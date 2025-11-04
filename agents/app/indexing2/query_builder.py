"""
Query Builder for Enhanced Table Column Field Types

This module provides query building capabilities that leverage the new field type
classification (dimension vs fact) to build better, more optimized queries.

Features:
- Field type-aware query building
- Dimension vs fact classification
- SQL generation with best practices
- Query optimization suggestions
- Performance considerations
"""

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
class QueryHint:
    """Query building hint for a column."""
    column_name: str
    field_type: str
    sql_suggestions: List[str]
    aggregation_functions: List[str]
    filter_operators: List[str]
    join_conditions: List[str]
    indexing_suggestions: List[str]
    performance_considerations: List[str]


@dataclass
class QueryTemplate:
    """Query template for different use cases."""
    template_name: str
    description: str
    sql_template: str
    required_field_types: List[str]
    optional_field_types: List[str]
    performance_notes: List[str]


class QueryBuilder:
    """
    Query builder that leverages field type classification for better query generation.
    
    This class provides:
    1. Field type-aware query building
    2. SQL generation with best practices
    3. Query optimization suggestions
    4. Performance considerations
    """
    
    def __init__(self):
        """Initialize the query builder."""
        self.query_templates = self._initialize_query_templates()
        logger.info("Query Builder initialized")
    
    def build_query_from_table_document(
        self,
        table_document: Dict[str, Any],
        query_type: str = "analytical",
        filters: Optional[Dict[str, Any]] = None,
        aggregations: Optional[List[str]] = None,
        group_by: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build a query from a table document using field type classification.
        
        Args:
            table_document: TABLE_DOCUMENT with field type information
            query_type: Type of query to build (analytical, transactional, reporting)
            filters: Optional filters to apply
            aggregations: Optional aggregation functions
            group_by: Optional GROUP BY columns
            order_by: Optional ORDER BY columns
            limit: Optional LIMIT clause
            
        Returns:
            Dictionary containing the generated query and metadata
        """
        logger.info(f"Building {query_type} query for table: {table_document.get('table_name', '')}")
        
        try:
            table_name = table_document.get("table_name", "")
            columns = table_document.get("columns", [])
            
            # Classify columns by field type
            classified_columns = self._classify_columns_by_field_type(columns)
            
            # Generate query based on type
            if query_type == "analytical":
                query = self._build_analytical_query(
                    table_name, classified_columns, filters, aggregations, group_by, order_by, limit
                )
            elif query_type == "transactional":
                query = self._build_transactional_query(
                    table_name, classified_columns, filters, order_by, limit
                )
            elif query_type == "reporting":
                query = self._build_reporting_query(
                    table_name, classified_columns, filters, aggregations, group_by, order_by, limit
                )
            else:
                raise ValueError(f"Unknown query type: {query_type}")
            
            # Add query hints and optimization suggestions
            query_hints = self._generate_query_hints(classified_columns)
            performance_suggestions = self._generate_performance_suggestions(classified_columns, query_type)
            
            return {
                "query": query,
                "query_type": query_type,
                "table_name": table_name,
                "field_type_classification": classified_columns,
                "query_hints": query_hints,
                "performance_suggestions": performance_suggestions,
                "optimization_notes": self._get_optimization_notes(query_type, classified_columns)
            }
            
        except Exception as e:
            logger.error(f"Error building query: {str(e)}")
            raise
    
    def _classify_columns_by_field_type(self, columns: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Classify columns by their field type."""
        classification = {
            "dimensions": [],
            "facts": [],
            "identifiers": [],
            "timestamps": [],
            "calculated": []
        }
        
        for column in columns:
            field_type = column.get("field_type", "dimension")
            
            if field_type == "dimension":
                classification["dimensions"].append(column)
            elif field_type == "fact":
                classification["facts"].append(column)
            elif field_type == "identifier":
                classification["identifiers"].append(column)
            elif field_type == "timestamp":
                classification["timestamps"].append(column)
            elif field_type == "calculated":
                classification["calculated"].append(column)
        
        return classification
    
    def _build_analytical_query(
        self,
        table_name: str,
        classified_columns: Dict[str, List[Dict[str, Any]]],
        filters: Optional[Dict[str, Any]],
        aggregations: Optional[List[str]],
        group_by: Optional[List[str]],
        order_by: Optional[List[str]],
        limit: Optional[int]
    ) -> str:
        """Build an analytical query optimized for dimensions and facts."""
        
        # Select clause - prioritize facts for aggregation
        select_parts = []
        
        if aggregations and classified_columns["facts"]:
            for fact in classified_columns["facts"]:
                fact_name = fact.get("name", "")
                for agg in aggregations:
                    select_parts.append(f"{agg}({fact_name}) AS {agg.lower()}_{fact_name}")
        else:
            # Default aggregations for facts
            for fact in classified_columns["facts"]:
                fact_name = fact.get("name", "")
                select_parts.append(f"SUM({fact_name}) AS total_{fact_name}")
                select_parts.append(f"COUNT({fact_name}) AS count_{fact_name}")
        
        # Add dimensions to SELECT
        for dimension in classified_columns["dimensions"]:
            select_parts.append(dimension.get("name", ""))
        
        # Add timestamps for time-based analysis
        for timestamp in classified_columns["timestamps"]:
            select_parts.append(timestamp.get("name", ""))
        
        select_clause = "SELECT " + ", ".join(select_parts) if select_parts else "SELECT *"
        
        # FROM clause
        from_clause = f"FROM {table_name}"
        
        # WHERE clause
        where_clause = ""
        if filters:
            where_conditions = []
            for column_name, filter_value in filters.items():
                if isinstance(filter_value, str):
                    where_conditions.append(f"{column_name} = '{filter_value}'")
                elif isinstance(filter_value, (int, float)):
                    where_conditions.append(f"{column_name} = {filter_value}")
                elif isinstance(filter_value, dict):
                    # Handle range filters
                    if "min" in filter_value and "max" in filter_value:
                        where_conditions.append(f"{column_name} BETWEEN {filter_value['min']} AND {filter_value['max']}")
            
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # GROUP BY clause
        group_by_clause = ""
        if group_by or classified_columns["dimensions"]:
            group_columns = group_by if group_by else [dim.get("name", "") for dim in classified_columns["dimensions"]]
            group_by_clause = "GROUP BY " + ", ".join(group_columns)
        
        # ORDER BY clause
        order_by_clause = ""
        if order_by:
            order_by_clause = "ORDER BY " + ", ".join(order_by)
        elif classified_columns["timestamps"]:
            # Default to ordering by timestamp
            timestamp_name = classified_columns["timestamps"][0].get("name", "")
            order_by_clause = f"ORDER BY {timestamp_name} DESC"
        
        # LIMIT clause
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        # Combine all clauses
        query_parts = [select_clause, from_clause, where_clause, group_by_clause, order_by_clause, limit_clause]
        query = " ".join([part for part in query_parts if part])
        
        return query
    
    def _build_transactional_query(
        self,
        table_name: str,
        classified_columns: Dict[str, List[Dict[str, Any]]],
        filters: Optional[Dict[str, Any]],
        order_by: Optional[List[str]],
        limit: Optional[int]
    ) -> str:
        """Build a transactional query optimized for identifiers and dimensions."""
        
        # Select clause - focus on identifiers and dimensions
        select_parts = []
        
        # Add identifiers first
        for identifier in classified_columns["identifiers"]:
            select_parts.append(identifier.get("name", ""))
        
        # Add dimensions
        for dimension in classified_columns["dimensions"]:
            select_parts.append(dimension.get("name", ""))
        
        # Add facts (but not aggregated)
        for fact in classified_columns["facts"]:
            select_parts.append(fact.get("name", ""))
        
        # Add timestamps
        for timestamp in classified_columns["timestamps"]:
            select_parts.append(timestamp.get("name", ""))
        
        select_clause = "SELECT " + ", ".join(select_parts) if select_parts else "SELECT *"
        
        # FROM clause
        from_clause = f"FROM {table_name}"
        
        # WHERE clause
        where_clause = ""
        if filters:
            where_conditions = []
            for column_name, filter_value in filters.items():
                if isinstance(filter_value, str):
                    where_conditions.append(f"{column_name} = '{filter_value}'")
                elif isinstance(filter_value, (int, float)):
                    where_conditions.append(f"{column_name} = {filter_value}")
            
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # ORDER BY clause
        order_by_clause = ""
        if order_by:
            order_by_clause = "ORDER BY " + ", ".join(order_by)
        elif classified_columns["timestamps"]:
            # Default to ordering by timestamp
            timestamp_name = classified_columns["timestamps"][0].get("name", "")
            order_by_clause = f"ORDER BY {timestamp_name} DESC"
        
        # LIMIT clause
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        # Combine all clauses
        query_parts = [select_clause, from_clause, where_clause, order_by_clause, limit_clause]
        query = " ".join([part for part in query_parts if part])
        
        return query
    
    def _build_reporting_query(
        self,
        table_name: str,
        classified_columns: Dict[str, List[Dict[str, Any]]],
        filters: Optional[Dict[str, Any]],
        aggregations: Optional[List[str]],
        group_by: Optional[List[str]],
        order_by: Optional[List[str]],
        limit: Optional[int]
    ) -> str:
        """Build a reporting query with comprehensive aggregations."""
        
        # Select clause - comprehensive aggregations
        select_parts = []
        
        # Add dimensions for grouping
        for dimension in classified_columns["dimensions"]:
            select_parts.append(dimension.get("name", ""))
        
        # Add comprehensive fact aggregations
        for fact in classified_columns["facts"]:
            fact_name = fact.get("name", "")
            select_parts.extend([
                f"SUM({fact_name}) AS total_{fact_name}",
                f"COUNT({fact_name}) AS count_{fact_name}",
                f"AVG({fact_name}) AS avg_{fact_name}",
                f"MAX({fact_name}) AS max_{fact_name}",
                f"MIN({fact_name}) AS min_{fact_name}"
            ])
        
        # Add timestamp for time-based reporting
        for timestamp in classified_columns["timestamps"]:
            select_parts.append(timestamp.get("name", ""))
        
        select_clause = "SELECT " + ", ".join(select_parts) if select_parts else "SELECT *"
        
        # FROM clause
        from_clause = f"FROM {table_name}"
        
        # WHERE clause
        where_clause = ""
        if filters:
            where_conditions = []
            for column_name, filter_value in filters.items():
                if isinstance(filter_value, str):
                    where_conditions.append(f"{column_name} = '{filter_value}'")
                elif isinstance(filter_value, (int, float)):
                    where_conditions.append(f"{column_name} = {filter_value}")
                elif isinstance(filter_value, dict):
                    if "min" in filter_value and "max" in filter_value:
                        where_conditions.append(f"{column_name} BETWEEN {filter_value['min']} AND {filter_value['max']}")
            
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # GROUP BY clause - use dimensions
        group_by_clause = ""
        if classified_columns["dimensions"]:
            dimension_names = [dim.get("name", "") for dim in classified_columns["dimensions"]]
            group_by_clause = "GROUP BY " + ", ".join(dimension_names)
        
        # ORDER BY clause
        order_by_clause = ""
        if order_by:
            order_by_clause = "ORDER BY " + ", ".join(order_by)
        elif classified_columns["timestamps"]:
            timestamp_name = classified_columns["timestamps"][0].get("name", "")
            order_by_clause = f"ORDER BY {timestamp_name} DESC"
        
        # LIMIT clause
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        # Combine all clauses
        query_parts = [select_clause, from_clause, where_clause, group_by_clause, order_by_clause, limit_clause]
        query = " ".join([part for part in query_parts if part])
        
        return query
    
    def _generate_query_hints(self, classified_columns: Dict[str, List[Dict[str, Any]]]) -> List[QueryHint]:
        """Generate query hints for each column type."""
        hints = []
        
        for field_type, columns in classified_columns.items():
            for column in columns:
                column_name = column.get("name", "")
                data_type = column.get("data_type", "")
                
                hint = QueryHint(
                    column_name=column_name,
                    field_type=field_type,
                    sql_suggestions=[],  # Not needed - using SQL pairs and instructions
                    aggregation_functions=self._get_aggregation_functions(field_type, data_type),
                    filter_operators=self._get_filter_operators(field_type, data_type),
                    join_conditions=self._get_join_conditions(field_type, column),
                    indexing_suggestions=self._get_indexing_suggestions(field_type, column),
                    performance_considerations=self._get_performance_considerations(field_type, column)
                )
                hints.append(hint)
        
        return hints
    
    def _get_sql_suggestions(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get SQL usage suggestions for a column."""
        # Not needed - using SQL pairs and instructions
        return []
    
    def _get_aggregation_functions(self, field_type: str, data_type: str) -> List[str]:
        """Get aggregation function suggestions."""
        if field_type == "fact":
            if data_type in ["INTEGER", "BIGINT", "DECIMAL", "FLOAT", "DOUBLE", "NUMERIC"]:
                return ["SUM", "COUNT", "AVG", "MAX", "MIN", "STDDEV", "VARIANCE"]
            else:
                return ["COUNT", "COUNT_DISTINCT"]
        else:
            return ["COUNT", "COUNT_DISTINCT"]
    
    def _get_filter_operators(self, field_type: str, data_type: str) -> List[str]:
        """Get appropriate filter operators for a column."""
        operators = ["=", "!=", "IS NULL", "IS NOT NULL"]
        
        if field_type == "fact":
            operators.extend([">", "<", ">=", "<=", "BETWEEN"])
        elif field_type == "dimension":
            operators.extend(["LIKE", "ILIKE", "IN", "NOT IN"])
        elif field_type == "timestamp":
            operators.extend([">", "<", ">=", "<=", "BETWEEN", "DATE_TRUNC"])
        
        return operators
    
    def _get_join_conditions(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get join condition suggestions."""
        if field_type == "identifier":
            column_name = column.get("name", "")
            return [
                f"Use {column_name} as foreign key in JOIN conditions",
                f"Create indexes on {column_name} for better join performance",
                f"Consider composite keys if multiple identifier columns exist"
            ]
        else:
            return ["Not typically used in JOIN conditions"]
    
    def _get_indexing_suggestions(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get indexing suggestions for a column."""
        column_name = column.get("name", "")
        suggestions = []
        
        if field_type == "identifier":
            suggestions.append(f"Create primary key or unique index on {column_name}")
        elif field_type == "dimension":
            suggestions.append(f"Consider index on {column_name} for frequent filtering")
        elif field_type == "timestamp":
            suggestions.append(f"Create index on {column_name} for date range queries")
        elif field_type == "fact":
            suggestions.append(f"Consider composite indexes with dimension columns for {column_name}")
        
        return suggestions
    
    def _get_performance_considerations(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get performance considerations for a column."""
        considerations = []
        
        if field_type == "fact":
            considerations.extend([
                "Use appropriate aggregation functions for better performance",
                "Consider materialized views for frequently aggregated data",
                "Use columnar storage for analytical workloads"
            ])
        elif field_type == "dimension":
            considerations.extend([
                "Use appropriate data types to minimize storage",
                "Consider denormalization for frequently accessed dimensions",
                "Use bitmap indexes for low-cardinality dimensions"
            ])
        elif field_type == "identifier":
            considerations.extend([
                "Use integer types for better join performance",
                "Consider surrogate keys for better performance",
                "Ensure proper indexing for foreign key relationships"
            ])
        elif field_type == "timestamp":
            considerations.extend([
                "Use appropriate timestamp data types",
                "Consider partitioning by date ranges",
                "Use date functions efficiently in queries"
            ])
        
        return considerations
    
    def _generate_performance_suggestions(
        self,
        classified_columns: Dict[str, List[Dict[str, Any]]],
        query_type: str
    ) -> List[str]:
        """Generate performance suggestions based on field types and query type."""
        suggestions = []
        
        if query_type == "analytical":
            if classified_columns["facts"]:
                suggestions.append("Consider using columnar storage for analytical workloads")
                suggestions.append("Use appropriate aggregation functions for better performance")
            
            if classified_columns["dimensions"]:
                suggestions.append("Consider bitmap indexes for low-cardinality dimensions")
                suggestions.append("Use appropriate data types to minimize storage")
        
        elif query_type == "transactional":
            if classified_columns["identifiers"]:
                suggestions.append("Ensure proper indexing on identifier columns")
                suggestions.append("Use integer types for better join performance")
            
            if classified_columns["timestamps"]:
                suggestions.append("Consider partitioning by date ranges")
                suggestions.append("Use appropriate timestamp data types")
        
        elif query_type == "reporting":
            suggestions.append("Consider materialized views for frequently accessed reports")
            suggestions.append("Use composite indexes combining dimensions and facts")
            suggestions.append("Consider denormalization for frequently accessed dimensions")
        
        return suggestions
    
    def _get_optimization_notes(self, query_type: str, classified_columns: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Get optimization notes for the query."""
        notes = []
        
        # Count columns by type
        fact_count = len(classified_columns["facts"])
        dimension_count = len(classified_columns["dimensions"])
        identifier_count = len(classified_columns["identifiers"])
        timestamp_count = len(classified_columns["timestamps"])
        
        if fact_count > 0:
            notes.append(f"Query includes {fact_count} fact column(s) - suitable for aggregation")
        
        if dimension_count > 0:
            notes.append(f"Query includes {dimension_count} dimension column(s) - suitable for grouping and filtering")
        
        if identifier_count > 0:
            notes.append(f"Query includes {identifier_count} identifier column(s) - suitable for joins")
        
        if timestamp_count > 0:
            notes.append(f"Query includes {timestamp_count} timestamp column(s) - suitable for time-based analysis")
        
        # Query type specific notes
        if query_type == "analytical":
            notes.append("Analytical query optimized for aggregation and grouping")
        elif query_type == "transactional":
            notes.append("Transactional query optimized for exact lookups and filtering")
        elif query_type == "reporting":
            notes.append("Reporting query optimized for comprehensive aggregations")
        
        return notes
    
    def _initialize_query_templates(self) -> List[QueryTemplate]:
        """Initialize query templates for different use cases."""
        templates = [
            QueryTemplate(
                template_name="analytical_summary",
                description="Analytical query for summarizing facts by dimensions",
                sql_template="SELECT {dimensions}, SUM({facts}) FROM {table} GROUP BY {dimensions}",
                required_field_types=["dimensions", "facts"],
                optional_field_types=["timestamps"],
                performance_notes=["Use indexes on dimension columns", "Consider materialized views for large datasets"]
            ),
            QueryTemplate(
                template_name="transactional_lookup",
                description="Transactional query for exact lookups using identifiers",
                sql_template="SELECT * FROM {table} WHERE {identifiers} = {values}",
                required_field_types=["identifiers"],
                optional_field_types=["dimensions", "facts", "timestamps"],
                performance_notes=["Ensure primary key or unique indexes", "Use integer types for identifiers"]
            ),
            QueryTemplate(
                template_name="time_series_analysis",
                description="Time series analysis using timestamps and facts",
                sql_template="SELECT {timestamps}, SUM({facts}) FROM {table} GROUP BY {timestamps} ORDER BY {timestamps}",
                required_field_types=["timestamps", "facts"],
                optional_field_types=["dimensions"],
                performance_notes=["Partition by date ranges", "Use date functions efficiently"]
            )
        ]
        
        return templates
