"""
LLM-Powered Definition Service with MCP Integration
Creates metrics, views, and calculated columns using LLMs and intelligent table matching
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod

from langchain.agents import AgentType, initialize_agent
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from app.core.dependencies import get_llm
# Import our models
from app.schemas.dbmodels import (
    Project, Table,  Metric, View, CalculatedColumn, 
    determine_change_type
)
from app.schemas.dbmodels import SQLColumn as Columns

from app.utils.history import ProjectManager
from app.service.models import UserExample,GeneratedDefinition,DefinitionType
import traceback

class TableMatchingTool(BaseTool):
    """Langchain tool for matching user descriptions to actual tables and columns using LLM semantic matching"""
    
    name: str = "table_matching"
    description: str = "Matches user descriptions to actual database tables and columns using semantic similarity"
    session: Any
    project_id: str
    llm: Any = None
    
    def __init__(self, session: Session, project_id: str, llm=None):
        super().__init__()
        self.session = session
        self.project_id = project_id
        self.llm = llm or get_llm()
    
    async def _arun(self, description: str) -> str:
        """Find matching tables and columns for a description using LLM semantic matching"""
        try:
            # Get all tables and columns for the project
            tables = self.session.query(Table).filter(Table.project_id == self.project_id).all()
            
            if not tables:
                return json.dumps([])
            
            # Prepare table and column information for LLM analysis
            table_data = []
            for table in tables:
                table_info = {
                    "table_name": table.name,
                    "display_name": table.display_name or table.name,
                    "description": table.description or "",
                    "columns": []
                }
                
                for column in table.columns:
                    table_info["columns"].append({
                        "name": column.name,
                        "display_name": column.display_name or column.name,
                        "data_type": column.data_type,
                        "description": column.description or ""
                    })
                
                table_data.append(table_info)
            
            # Use LLM to find the most relevant tables and columns
            matches = await self._find_semantic_matches(description, table_data)
            return json.dumps(matches)
            
        except Exception as e:
            print(f"Error in table matching: {str(e)}")
            traceback.print_exc()
            # Fallback to empty result
            return json.dumps([])
    
    def _run(self, description: str) -> str:
        """Synchronous version - calls async method"""
        return asyncio.run(self._arun(description))
    
    async def _find_semantic_matches(self, description: str, table_data: List[Dict]) -> List[Dict]:
        """Use LLM to find semantically relevant tables and columns"""
        
        system_prompt = """You are an expert data analyst specializing in database schema analysis and semantic matching.
        Your task is to identify the most relevant database tables and columns based on a user's description.
        
        Analyze the user's description and match it to the most semantically relevant tables and columns.
        Consider:
        1. Business domain alignment
        2. Semantic similarity in names and descriptions
        3. Data type relevance
        4. Functional relationships
        
        Return only the most relevant matches with high confidence scores."""
        
        user_prompt = """
        User Description: {description}
        
        Available Tables and Columns:
        {table_data}
        
        Analyze the user description and identify the most relevant tables and columns.
        Return a JSON response with the following structure:
        {{
            "matches": [
                {{
                    "table_name": "exact_table_name",
                    "table_description": "table description",
                    "relevance_score": 0.95,
                    "reasoning": "explanation of why this table is relevant",
                    "columns": [
                        {{
                            "name": "exact_column_name",
                            "type": "data_type",
                            "description": "column description",
                            "relevance_score": 0.92,
                            "reasoning": "explanation of why this column is relevant"
                        }}
                    ]
                }}
            ]
        }}
        
        Guidelines:
        - Only include tables with relevance_score >= 0.7
        - Only include columns with relevance_score >= 0.6
        - Provide clear reasoning for each match
        - Focus on semantic meaning, not just keyword matching
        - Consider business context and data relationships
        """
        
        formatted_inputs = {
            "description": description,
            "table_data": json.dumps(table_data, indent=2)
        }
        
        try:
            # Create the prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", user_prompt)
            ])
            
            # Create the chain
            chain = (
                prompt 
                | self.llm 
                | StrOutputParser()
            )
            
            # Execute the chain
            response = await chain.ainvoke(formatted_inputs)
            
            # Parse the response
            result = json.loads(response)
            return result.get("matches", [])
            
        except Exception as e:
            print(f"Error in LLM semantic matching: {str(e)}")
            traceback.print_exc()
            # Fallback to simple keyword matching
            return self._fallback_keyword_matching(description, table_data)
    
    def _fallback_keyword_matching(self, description: str, table_data: List[Dict]) -> List[Dict]:
        """Fallback to simple keyword matching if LLM fails"""
        description_lower = description.lower()
        matches = []
        
        for table_info in table_data:
            table_matched = False
            table_name = table_info["table_name"].lower()
            display_name = table_info.get("display_name", "").lower()
            table_desc = table_info.get("description", "").lower()
            
            # Check if table matches
            if (table_name in description_lower or 
                display_name in description_lower or 
                table_desc in description_lower):
                table_matched = True
            
            relevant_columns = []
            for column in table_info["columns"]:
                col_name = column["name"].lower()
                col_display = column.get("display_name", "").lower()
                col_desc = column.get("description", "").lower()
                
                if (col_name in description_lower or 
                    col_display in description_lower or 
                    col_desc in description_lower):
                    relevant_columns.append({
                        "name": column["name"],
                        "type": column["data_type"],
                        "description": column.get("description", ""),
                        "relevance_score": 0.8,
                        "reasoning": "Keyword match fallback"
                    })
            
            if table_matched or relevant_columns:
                matches.append({
                    "table_name": table_info["table_name"],
                    "table_description": table_info.get("description", ""),
                    "relevance_score": 0.8 if table_matched else 0.6,
                    "reasoning": "Keyword match fallback",
                    "columns": relevant_columns
                })
        
        return matches


class LLMDefinitionGenerator:
    """LLM-powered generator for creating enhanced definitions"""
    
    def __init__(self, llm=None):
        self.client = llm or get_llm()
    
    async def generate_metric_definition(self, user_example: UserExample, 
                                       context: Dict[str, Any]) -> GeneratedDefinition:
        """Generate enhanced metric definition from user example"""
        
        system_prompt = """You are an expert data analyst specializing in creating business metrics. 
        Given a user example and project context, create a comprehensive metric definition including:
        1. Enhanced name and display name
        2. Detailed description
        3. Optimized SQL query
        4. Chain of thought explaining the metric logic
        5. Related tables and columns
        6. Metadata and suggestions
        
        Focus on business value and analytical accuracy."""
        
        user_prompt = """
        Create a metric definition from this user example:
        
        User Example:
        - Name: {name}
        - Description: {description}
        - SQL: {sql}
        - Context: {additional_context}
        
        Project Context:
        - Tables: {tables}
        - Existing Metrics: {existing_metrics}
        - Business Context: {business_context}
        
        Return ONLY a JSON object with the following structure (no markdown formatting, no code blocks):
        {{
            "name": "technical_name",
            "display_name": "Business Display Name",
            "description": "Detailed business description",
            "sql_query": "SELECT optimized SQL query",
            "chain_of_thought": "Step-by-step explanation of the metric logic",
            "related_tables": ["table1", "table2"],
            "related_columns": ["column1", "column2"],
            "metadata": {{
                "metric_type": "count|sum|avg|percentage|custom",
                "aggregation_type": "sum|avg|count|max|min",
                "format_string": "formatting hint",
                "business_category": "performance|compliance|efficiency",
                "update_frequency": "real-time|daily|weekly|monthly",
                "data_quality_requirements": ["requirement1", "requirement2"]
            }},
            "confidence_score": 0.95,
            "suggestions": ["suggestion1", "suggestion2"]
        }}
        
        IMPORTANT: Return ONLY the JSON object, no markdown formatting, no code blocks, no additional text.
        If the Percenatges or rates are there in sql query, Always use cast to decimal and round the value to 2 decimal places with Case When and Muliply by 100.
        """
        formatted_inputs = {
            "name": user_example.name,
            "description": user_example.description,
            "sql": user_example.sql if user_example.sql else "Not provided",
            "additional_context": user_example.additional_context if user_example.additional_context else "Not provided",
            "tables": json.dumps(context.get("tables", {}), indent=2),
            "existing_metrics": json.dumps(context.get("existing_metrics", {}), indent=2),
            "business_context": json.dumps(context.get("business_context", {}), indent=2)
        }
        
        response = await self._call_llm(system_prompt, user_prompt,formatted_inputs)
        print("response: ", response)
        return self._parse_response(response, DefinitionType.METRIC)
    
    async def generate_view_definition(self, user_example: UserExample, 
                                     context: Dict[str, Any]) -> GeneratedDefinition:
        """Generate enhanced view definition from user example"""
        
        system_prompt = """You are an expert database architect specializing in creating analytical views.
        Given a user example and project context, create a comprehensive view definition that:
        1. Optimizes data access patterns
        2. Provides clear business value
        3. Follows best practices for view design
        4. Includes proper documentation and metadata
        
        Focus on performance, maintainability, and business utility."""
        
        user_prompt = """
        Create a view definition from this user example:
        
        User Example:
        - Name: {name}
        - Description: {description}
        - SQL: {sql}
        - Context: {additional_context}
        
        Project Context:
        - Tables: {tables}
        - Data Lineage: {data_lineage}
        - Business Context: {business_context}
        
        Return ONLY a JSON object with the following structure (no markdown formatting, no code blocks):
        {{
            "name": "view_name",
            "display_name": "Business View Name",
            "description": "Detailed view description and purpose",
            "sql_query": "CREATE VIEW optimized_view_sql",
            "chain_of_thought": "Step-by-step explanation of view design decisions",
            "related_tables": ["base_table1", "joined_table2"],
            "related_columns": ["key_column1", "aggregated_column2"],
            "metadata": {{
                "view_type": "filtered|aggregated|joined|materialized",
                "refresh_strategy": "on-demand|scheduled|real-time",
                "performance_impact": "low|medium|high",
                "business_use_case": "reporting|analytics|operational",
                "dependencies": ["table1", "view2"],
                "security_considerations": ["pii_data", "access_controls"]
            }},
            "confidence_score": 0.90,
            "suggestions": ["performance_optimization1", "business_enhancement2"]
        }}
        
        IMPORTANT: Return ONLY the JSON object, no markdown formatting, no code blocks, no additional text.
        If the Percenatges or rates are there in sql query, Always use cast to decimal and round the value to 2 decimal places with Case When and Muliply by 100.
        """
        formatted_inputs = {
        "name": user_example.name,
        "description": user_example.description,
        "sql": user_example.sql if user_example.sql else "Not provided",
        "additional_context": user_example.additional_context if user_example.additional_context else "Not provided",
        "tables": json.dumps(context.get("tables", {}), indent=2),
        "data_lineage": json.dumps(context.get("data_lineage", {}), indent=2),
        "business_context": json.dumps(context.get("business_context", {}), indent=2)
        }
        
        response = await self._call_llm(system_prompt, user_prompt,formatted_inputs)
        print("response: ", response)
        return self._parse_response(response, DefinitionType.VIEW)
    
    async def generate_calculated_column_definition(self, user_example: UserExample, 
                                                  context: Dict[str, Any]) -> GeneratedDefinition:
        """Generate enhanced calculated column definition from user example"""
        
        system_prompt = """You are an expert data engineer specializing in calculated columns and derived fields.
        Given a user example and project context, create a comprehensive calculated column definition that:
        1. Implements correct business logic
        2. Handles edge cases and null values
        3. Optimizes for performance
        4. Provides clear documentation
        
        Focus on accuracy, performance, and maintainability."""
        
        user_prompt = """
        Create a calculated column definition from this user example:
        
        User Example:
        - Name: {name}
        - Description: {description}
        - SQL: {sql}
        - Context: {additional_context}
        
        Project Context:
        - Tables: {tables}
        - Data Lineage: {data_lineage}
        - Business Rules: {business_context}
        
        Return ONLY a JSON object with the following structure (no markdown formatting, no code blocks):
        {{
            "name": "calculated_column_name",
            "display_name": "Business Column Name",
            "description": "Detailed calculation description and business purpose",
            "sql_query": "calculation_formula_with_null_handling",
            "chain_of_thought": "Step-by-step explanation of calculation logic",
            "related_tables": ["source_table"],
            "related_columns": ["input_column1", "input_column2"],
            "metadata": {{
                "data_type": "INTEGER|VARCHAR|BOOLEAN|DECIMAL|DATE",
                "calculation_type": "arithmetic|conditional|date|string|aggregation",
                "dependencies": ["column1", "column2"],
                "null_handling": "description of null value handling",
                "performance_impact": "low|medium|high",
                "validation_rules": ["rule1", "rule2"],
                "business_rules_applied": ["rule1", "rule2"]
            }},
            "confidence_score": 0.88,
            "suggestions": ["optimization1", "validation2"]
        }}
        
        IMPORTANT: Return ONLY the JSON object, no markdown formatting, no code blocks, no additional text.
        """
        formatted_inputs = {
        "name": user_example.name,
        "description": user_example.description,
        "sql": user_example.sql if user_example.sql else "Not provided",
        "additional_context": user_example.additional_context if user_example.additional_context else "Not provided",
        "tables": json.dumps(context.get("tables", {}), indent=2),
        "data_lineage": json.dumps(context.get("data_lineage", {}), indent=2),
        "business_context": json.dumps(context.get("business_context", {}), indent=2)
        }

        
        response = await self._call_llm(system_prompt, user_prompt,formatted_inputs)
        print("response: ", response)
        return self._parse_response(response, DefinitionType.CALCULATED_COLUMN)
    
    async def _call_llm(self, system_prompt: str, user_prompt: str,formatted_inputs: Dict[str, Any]) -> str:
        """Call LLM with prompts and return response using Langchain pipe pattern"""
        try:
            # Create the prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", user_prompt)
            ])
            
            # Create the chain using pipe operator pattern
            chain = (
                prompt 
                | self.client 
                | StrOutputParser()
            )
            print("formatted_inputs",formatted_inputs)
            
            # Execute the chain
            response = await chain.ainvoke(formatted_inputs)
            return response
            
        except Exception as e:
        # --- THIS IS THE CRITICAL DIAGNOSTIC CHANGE ---
            print("--- !!! AN EXCEPTION OCCURRED !!! ---")
            print(f"Python Exception Type: {type(e)}")
            print(f"Python Exception repr: {repr(e)}")
            print("--- FULL TRACEBACK ---")
            
            # This will print the complete error stack trace to your console
            traceback.print_exc() 
            
            print("--- END TRACEBACK ---")
            
            # Re-raise the original exception to maintain the error context
            raise e

    
    def _parse_response(self, response: str, definition_type: DefinitionType) -> GeneratedDefinition:
        """Parse LLM response into GeneratedDefinition"""
        try:
            # First, try to parse the response as-is
            data = json.loads(response)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from markdown code blocks
            try:
                import re
                # Look for JSON wrapped in markdown code blocks
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)
                    data = json.loads(json_content)
                else:
                    # Try to extract just the JSON object from the response
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(0)
                        data = json.loads(json_content)
                    else:
                        raise Exception("No valid JSON found in response")
            except (json.JSONDecodeError, Exception) as e:
                print(f"Failed to parse LLM response after extraction attempts: {str(e)}")
                print(f"Original response: {response[:500]}...")
                raise Exception(f"Failed to parse LLM response: {str(e)}")
        
        return GeneratedDefinition(
            definition_type=definition_type,
            name=data.get("name", ""),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            sql_query=data.get("sql_query", ""),
            chain_of_thought=data.get("chain_of_thought", ""),
            related_tables=data.get("related_tables", []),
            related_columns=data.get("related_columns", []),
            metadata=data.get("metadata", {}),
            confidence_score=data.get("confidence_score", 0.0),
            suggestions=data.get("suggestions", [])
        )


class DefinitionValidationService:
    """Service for validating generated definitions"""
    
    def __init__(self, session: Session, project_id: str):
        self.session = session
        self.project_id = project_id
    
    def validate_definition(self, definition: GeneratedDefinition) -> Tuple[bool, List[str]]:
        """Validate generated definition and return validation result"""
        errors = []
        
        # Check name uniqueness
        if not self._is_name_unique(definition):
            errors.append(f"Name '{definition.name}' already exists in the project")
        
        # Validate SQL syntax (basic check)
        if not self._validate_sql_syntax(definition.sql_query):
            errors.append("SQL query has syntax issues")
        
        # Check table and column references
        table_errors = self._validate_table_references(definition.related_tables)
        column_errors = self._validate_column_references(definition.related_columns)
        
        errors.extend(table_errors)
        errors.extend(column_errors)
        
        # Check confidence score
        if definition.confidence_score < 0.7:
            errors.append(f"Low confidence score: {definition.confidence_score}")
        
        return len(errors) == 0, errors
    
    def _is_name_unique(self, definition: GeneratedDefinition) -> bool:
        """Check if definition name is unique in project"""
        if definition.definition_type == DefinitionType.METRIC:
            existing = self.session.query(Metric).join(Table).filter(
                Table.project_id == self.project_id,
                Metric.name == definition.name
            ).first()
        elif definition.definition_type == DefinitionType.VIEW:
            existing = self.session.query(View).join(Table).filter(
                Table.project_id == self.project_id,
                View.name == definition.name
            ).first()
        else:  # CALCULATED_COLUMN
            existing = self.session.query(Columns).join(Table).filter(
                Table.project_id == self.project_id,
                Columns.name == definition.name,
                Columns.column_type == 'calculated_column'
            ).first()
        
        return existing is None
    
    def _validate_sql_syntax(self, sql: str) -> bool:
        """Basic SQL syntax validation"""
        # This is a simplified check - in production, use a proper SQL parser
        sql_lower = sql.lower().strip()
        
        # Check for basic SQL structure
        if not sql_lower:
            return False
        
        # Basic keyword checks
        valid_starts = ['select', 'create view', 'case when', 'datediff', 'count', 'sum', 'avg']
        return any(sql_lower.startswith(start) for start in valid_starts)
    
    def _validate_table_references(self, table_names: List[str]) -> List[str]:
        """Validate that referenced tables exist"""
        errors = []
        existing_tables = {
            table.name for table in 
            self.session.query(Table).filter(Table.project_id == self.project_id).all()
        }
        
        for table_name in table_names:
            if table_name not in existing_tables:
                errors.append(f"Referenced table '{table_name}' does not exist")
        
        return errors
    
    def _validate_column_references(self, column_names: List[str]) -> List[str]:
        """Validate that referenced columns exist"""
        errors = []
        existing_columns = {
            column.name for table in 
            self.session.query(Table).filter(Table.project_id == self.project_id).all()
            for column in table.columns
        }
        
        for column_name in column_names:
            if column_name not in existing_columns:
                errors.append(f"Referenced column '{column_name}' does not exist")
        
        return errors

# ============================================================================
# MDL SCHEMA GENERATION UTILITIES
# ============================================================================

class MDLSchemaGenerator:
    """Utility class for appending LLM-generated definitions to existing MDL schema"""
    
    @staticmethod
    def append_definitions_to_mdl(
        existing_mdl: Dict[str, Any],
        definitions: List[GeneratedDefinition],
        project_id: str
    ) -> Dict[str, Any]:
        """
        Append LLM-generated definitions to existing MDL schema
        
        Args:
            existing_mdl: Existing MDL schema dictionary
            definitions: List of GeneratedDefinition objects to append
            project_id: Project identifier
            
        Returns:
            Updated MDL schema dictionary
        """
        # Create a copy of the existing MDL to avoid modifying the original
        updated_mdl = existing_mdl.copy()
        
        # Ensure all required arrays exist
        if "models" not in updated_mdl:
            updated_mdl["models"] = []
        if "views" not in updated_mdl:
            updated_mdl["views"] = []
        if "metrics" not in updated_mdl:
            updated_mdl["metrics"] = []
        if "relationships" not in updated_mdl:
            updated_mdl["relationships"] = []
        if "cumulativeMetrics" not in updated_mdl:
            updated_mdl["cumulativeMetrics"] = []
        if "enumDefinitions" not in updated_mdl:
            updated_mdl["enumDefinitions"] = []
        
        # Process each definition
        for definition in definitions:
            if definition.definition_type == DefinitionType.METRIC:
                updated_mdl["metrics"].append(
                    MDLSchemaGenerator._convert_metric_to_mdl(definition)
                )
            elif definition.definition_type == DefinitionType.VIEW:
                updated_mdl["views"].append(
                    MDLSchemaGenerator._convert_view_to_mdl(definition)
                )
            elif definition.definition_type == DefinitionType.CALCULATED_COLUMN:
                # For calculated columns, we need to find the appropriate model
                # and add the calculated column to it, or create a new model if needed
                MDLSchemaGenerator._append_calculated_column_to_mdl(updated_mdl, definition)
        
        return updated_mdl
    
    @staticmethod
    def append_definitions_to_mdl_from_context(
        existing_mdl: Dict[str, Any],
        definitions: List[GeneratedDefinition],
        project_context: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """
        Append LLM-generated definitions to existing MDL schema with project context
        
        Args:
            existing_mdl: Existing MDL schema dictionary
            definitions: List of GeneratedDefinition objects to append
            project_context: Project context with tables and metadata
            project_id: Project identifier
            
        Returns:
            Updated MDL schema dictionary
        """
        # First, ensure all tables from project context are in the MDL
        updated_mdl = MDLSchemaGenerator._ensure_tables_in_mdl(existing_mdl, project_context)
        
        # Then append the definitions
        return MDLSchemaGenerator.append_definitions_to_mdl(updated_mdl, definitions, project_id)
    
    @staticmethod
    def _convert_metric_to_mdl(definition: GeneratedDefinition) -> Dict[str, Any]:
        """Convert a GeneratedDefinition metric to MDL metric format"""
        
        # Extract base object from related tables
        base_object = definition.related_tables[0] if definition.related_tables else "unknown_table"
        
        # Create dimensions from related columns
        dimensions = []
        for column_name in definition.related_columns:
            # Extract table name if column is fully qualified
            if "." in column_name:
                table_name, col_name = column_name.split(".", 1)
            else:
                col_name = column_name
            
            dimensions.append({
                "name": col_name,
                "type": "VARCHAR",  # Default type, could be enhanced with metadata
                "properties": {
                    "description": f"Dimension for {definition.name} metric"
                }
            })
        
        # Create measure from the metric itself
        measures = [{
            "name": definition.name,
            "type": "DECIMAL",  # Default for numeric metrics
            "properties": {
                "description": definition.description,
                "display_name": definition.display_name,
                "aggregation_type": definition.metadata.get("aggregation_type", "custom"),
                "metric_type": definition.metadata.get("metric_type", "custom"),
                "business_category": definition.metadata.get("business_category", "performance"),
                "update_frequency": definition.metadata.get("update_frequency", "daily"),
                "confidence_score": str(definition.confidence_score),
                "chain_of_thought": definition.chain_of_thought
            }
        }]
        
        # Add time grain if there are date/time columns
        time_grain = []
        for column_name in definition.related_columns:
            if any(time_keyword in column_name.lower() for time_keyword in ["date", "time", "created", "updated"]):
                time_grain.append({
                    "name": f"{column_name}_grain",
                    "refColumn": column_name,
                    "dateParts": ["YEAR", "QUARTER", "MONTH", "WEEK", "DAY"]
                })
        
        return {
            "name": definition.name,
            "baseObject": base_object,
            "dimension": dimensions,
            "measure": measures,
            "timeGrain": time_grain,
            "cached": False,
            "properties": {
                "display_name": definition.display_name,
                "description": definition.description,
                "sql_query": definition.sql_query,
                "chain_of_thought": definition.chain_of_thought,
                "related_tables": ",".join(definition.related_tables),
                "related_columns": ",".join(definition.related_columns),
                "confidence_score": str(definition.confidence_score),
                "suggestions": ",".join(definition.suggestions),
                **definition.metadata
            }
        }
    
    @staticmethod
    def _convert_view_to_mdl(definition: GeneratedDefinition) -> Dict[str, Any]:
        """Convert a GeneratedDefinition view to MDL view format"""
        
        return {
            "name": definition.name,
            "statement": definition.sql_query,
            "properties": {
                "display_name": definition.display_name,
                "description": definition.description,
                "chain_of_thought": definition.chain_of_thought,
                "related_tables": ",".join(definition.related_tables),
                "related_columns": ",".join(definition.related_columns),
                "confidence_score": str(definition.confidence_score),
                "suggestions": ",".join(definition.suggestions),
                "view_type": definition.metadata.get("view_type", "custom"),
                "refresh_strategy": definition.metadata.get("refresh_strategy", "on-demand"),
                "performance_impact": definition.metadata.get("performance_impact", "medium"),
                "business_use_case": definition.metadata.get("business_use_case", "reporting"),
                **definition.metadata
            }
        }
    
    @staticmethod
    def _append_calculated_column_to_mdl(mdl: Dict[str, Any], definition: GeneratedDefinition) -> None:
        """Append a calculated column to the appropriate model in MDL"""
        
        # Get the base table for this calculated column
        base_table = definition.related_tables[0] if definition.related_tables else "unknown_table"
        
        # Find if the model already exists
        existing_model = None
        for model in mdl["models"]:
            if model.get("name") == base_table or model.get("baseObject") == base_table:
                existing_model = model
                break
        
        # Create the calculated column
        calculated_column = {
            "name": definition.name,
            "type": definition.metadata.get("data_type", "VARCHAR"),
            "isCalculated": True,
            "expression": definition.sql_query,
            "properties": {
                "display_name": definition.display_name,
                "description": definition.description,
                "business_description": definition.description,
                "calculation_type": definition.metadata.get("calculation_type", "custom"),
                "dependencies": ",".join(definition.metadata.get("dependencies", [])),
                "null_handling": definition.metadata.get("null_handling", "Returns NULL if input is NULL"),
                "performance_impact": definition.metadata.get("performance_impact", "low"),
                "validation_rules": ",".join(definition.metadata.get("validation_rules", [])),
                "business_rules_applied": ",".join(definition.metadata.get("business_rules_applied", [])),
                "confidence_score": str(definition.confidence_score),
                "chain_of_thought": definition.chain_of_thought,
                "suggestions": ",".join(definition.suggestions)
            }
        }
        
        if existing_model:
            # Add the calculated column to the existing model
            if "columns" not in existing_model:
                existing_model["columns"] = []
            existing_model["columns"].append(calculated_column)
            
            # Update model properties to indicate it has calculated columns
            if "properties" not in existing_model:
                existing_model["properties"] = {}
            existing_model["properties"]["has_calculated_columns"] = "true"
            existing_model["properties"]["calculated_columns"] = existing_model["properties"].get("calculated_columns", "") + f",{definition.name}"
        else:
            # Create a new model for this calculated column
            new_model = {
                "name": base_table,
                "baseObject": base_table,
                "columns": [calculated_column],
                "properties": {
                    "description": f"Model containing calculated column {definition.name}",
                    "calculated_column_name": definition.name,
                    "has_calculated_columns": "true",
                    "calculated_columns": definition.name
                }
            }
            mdl["models"].append(new_model)
    
    @staticmethod
    def _ensure_tables_in_mdl(mdl: Dict[str, Any], project_context: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all tables from project context are present in the MDL models"""
        
        tables = project_context.get("tables", {})
        existing_model_names = {model.get("name") for model in mdl.get("models", [])}
        
        for table_name, table_info in tables.items():
            if table_name not in existing_model_names:
                # Create a new model for this table
                model = {
                    "name": table_name,
                    "baseObject": table_name,
                    "columns": [],
                    "properties": {
                        "description": table_info.get("description", ""),
                        "display_name": table_info.get("display_name", table_name),
                        "business_purpose": table_info.get("business_purpose", ""),
                        "update_frequency": table_info.get("update_frequency", "unknown"),
                        "data_retention": table_info.get("data_retention", ""),
                        "primary_use_cases": ",".join(table_info.get("primary_use_cases", [])),
                        "key_relationships": ",".join(table_info.get("key_relationships", [])),
                        "access_patterns": ",".join(table_info.get("access_patterns", [])),
                        "performance_considerations": ",".join(table_info.get("performance_considerations", []))
                    }
                }
                
                # Convert columns
                columns = table_info.get("columns", [])
                for column_info in columns:
                    column = {
                        "name": column_info["name"],
                        "type": column_info["type"],
                        "notNull": not column_info.get("nullable", True),
                        "properties": {
                            "description": column_info.get("description", ""),
                            "display_name": column_info.get("display_name", column_info["name"]),
                            "business_description": column_info.get("business_description", ""),
                            "usage_type": column_info.get("usage_type", "attribute"),
                            "example_values": ",".join(column_info.get("example_values", [])),
                            "business_rules": ",".join(column_info.get("business_rules", [])),
                            "data_quality_checks": ",".join(column_info.get("data_quality_checks", [])),
                            "related_concepts": ",".join(column_info.get("related_concepts", [])),
                            "privacy_classification": column_info.get("privacy_classification", "public"),
                            "aggregation_suggestions": ",".join(column_info.get("aggregation_suggestions", [])),
                            "filtering_suggestions": ",".join(column_info.get("filtering_suggestions", []))
                        }
                    }
                    
                    # Handle calculated columns
                    if column_info.get("isCalculated", False):
                        column["isCalculated"] = True
                        column["expression"] = column_info.get("expression", "")
                    
                    model["columns"].append(column)
                
                mdl["models"].append(model)
        
        return mdl
    
    @staticmethod
    def create_initial_mdl_from_context(
        project_context: Dict[str, Any],
        project_id: str,
        catalog_name: Optional[str] = None,
        schema_name: str = "public"
    ) -> Dict[str, Any]:
        """
        Create initial MDL schema from project context (tables, existing metrics, etc.)
        This is used when starting with no existing MDL
        
        Args:
            project_context: Project context dictionary with tables and metadata
            project_id: Project identifier
            catalog_name: Catalog name
            schema_name: Schema name
            
        Returns:
            Initial MDL schema dictionary
        """
        catalog = catalog_name or f"{project_id}_catalog"
        
        mdl = {
            "catalog": catalog,
            "schema": schema_name,
            "models": [],
            "views": [],
            "relationships": [],
            "metrics": [],
            "cumulativeMetrics": [],
            "enumDefinitions": []
        }
        
        # Convert tables to models
        tables = project_context.get("tables", {})
        for table_name, table_info in tables.items():
            model = {
                "name": table_name,
                "baseObject": table_name,
                "columns": [],
                "properties": {
                    "description": table_info.get("description", ""),
                    "display_name": table_info.get("display_name", table_name),
                    "business_purpose": table_info.get("business_purpose", ""),
                    "update_frequency": table_info.get("update_frequency", "unknown"),
                    "data_retention": table_info.get("data_retention", ""),
                    "primary_use_cases": ",".join(table_info.get("primary_use_cases", [])),
                    "key_relationships": ",".join(table_info.get("key_relationships", [])),
                    "access_patterns": ",".join(table_info.get("access_patterns", [])),
                    "performance_considerations": ",".join(table_info.get("performance_considerations", []))
                }
            }
            
            # Convert columns
            columns = table_info.get("columns", [])
            for column_info in columns:
                column = {
                    "name": column_info["name"],
                    "type": column_info["type"],
                    "notNull": not column_info.get("nullable", True),
                    "properties": {
                        "description": column_info.get("description", ""),
                        "display_name": column_info.get("display_name", column_info["name"]),
                        "business_description": column_info.get("business_description", ""),
                        "usage_type": column_info.get("usage_type", "attribute"),
                        "example_values": ",".join(column_info.get("example_values", [])),
                        "business_rules": ",".join(column_info.get("business_rules", [])),
                        "data_quality_checks": ",".join(column_info.get("data_quality_checks", [])),
                        "related_concepts": ",".join(column_info.get("related_concepts", [])),
                        "privacy_classification": column_info.get("privacy_classification", "public"),
                        "aggregation_suggestions": ",".join(column_info.get("aggregation_suggestions", [])),
                        "filtering_suggestions": ",".join(column_info.get("filtering_suggestions", []))
                    }
                }
                
                # Handle calculated columns
                if column_info.get("isCalculated", False):
                    column["isCalculated"] = True
                    column["expression"] = column_info.get("expression", "")
                
                model["columns"].append(column)
            
            mdl["models"].append(model)
        
        # Convert existing metrics
        existing_metrics = project_context.get("existing_metrics", {})
        for metric_name, metric_description in existing_metrics.items():
            metric = {
                "name": metric_name,
                "baseObject": "unknown_table",  # Would need to be determined from context
                "dimension": [],
                "measure": [{
                    "name": metric_name,
                    "type": "DECIMAL",
                    "properties": {
                        "description": metric_description,
                        "display_name": metric_name.replace("_", " ").title(),
                        "metric_type": "custom"
                    }
                }],
                "properties": {
                    "description": metric_description,
                    "display_name": metric_name.replace("_", " ").title(),
                    "source": "existing_metric"
                }
            }
            mdl["metrics"].append(metric)
        
        return mdl
    
    @staticmethod
    def merge_mdl_schemas(schemas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple MDL schemas into one
        
        Args:
            schemas: List of MDL schema dictionaries
            
        Returns:
            Merged MDL schema
        """
        if not schemas:
            return {}
        
        # Use the first schema as base
        merged = schemas[0].copy()
        
        # Merge all other schemas
        for schema in schemas[1:]:
            # Merge models
            merged["models"].extend(schema.get("models", []))
            # Merge views
            merged["views"].extend(schema.get("views", []))            
            # Merge relationships
            merged["relationships"].extend(schema.get("relationships", []))
            # Merge metrics
            merged["metrics"].extend(schema.get("metrics", []))
            # Merge cumulative metrics
            merged["cumulativeMetrics"].extend(schema.get("cumulativeMetrics", []))            
            # Merge enum definitions
            merged["enumDefinitions"].extend(schema.get("enumDefinitions", []))
        return merged
    
    @staticmethod
    def validate_mdl_schema(mdl: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate MDL schema against basic requirements
        
        Args:
            mdl: MDL schema dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        if "catalog" not in mdl:
            errors.append("Missing required field: catalog")
        if "schema" not in mdl:
            errors.append("Missing required field: schema")
        
        # Check catalog and schema are not empty
        if not mdl.get("catalog", "").strip():
            errors.append("Catalog name cannot be empty")
        if not mdl.get("schema", "").strip():
            errors.append("Schema name cannot be empty")
        
        # Validate models
        for i, model in enumerate(mdl.get("models", [])):
            if "name" not in model:
                errors.append(f"Model {i}: Missing required field 'name'")
            elif not model["name"].strip():
                errors.append(f"Model {i}: Name cannot be empty")
            
            # Check columns
            for j, column in enumerate(model.get("columns", [])):
                if "name" not in column:
                    errors.append(f"Model {model.get('name', i)} Column {j}: Missing required field 'name'")
                if "type" not in column:
                    errors.append(f"Model {model.get('name', i)} Column {j}: Missing required field 'type'")
        
        # Validate metrics
        for i, metric in enumerate(mdl.get("metrics", [])):
            if "name" not in metric:
                errors.append(f"Metric {i}: Missing required field 'name'")
            if "baseObject" not in metric:
                errors.append(f"Metric {i}: Missing required field 'baseObject'")
            if "dimension" not in metric:
                errors.append(f"Metric {i}: Missing required field 'dimension'")
            if "measure" not in metric:
                errors.append(f"Metric {i}: Missing required field 'measure'")
        
        # Validate views
        for i, view in enumerate(mdl.get("views", [])):
            if "name" not in view:
                errors.append(f"View {i}: Missing required field 'name'")
            if "statement" not in view:
                errors.append(f"View {i}: Missing required field 'statement'")
        
        return len(errors) == 0, errors

    @staticmethod
    async def process_and_store_mdl_with_definitions(
        existing_mdl: Dict[str, Any],
        definitions: List[GeneratedDefinition],
        project_context: Dict[str, Any],
        project_id: str,
        document_store: Any,
        table_doc_store: Any,
        embedder: Any = None
    ) -> Dict[str, Any]:
        """
        Complete workflow: Append definitions to MDL and store using table_description.py
        This integrates with schema_manager.py and table_description.py
        
        Args:
            existing_mdl: Existing MDL schema
            definitions: LLM-generated definitions to append
            project_context: Project context
            project_id: Project identifier
            document_store: ChromaDB document store for schema documentation
            table_doc_store: ChromaDB document store for table descriptions
            embedder: Optional embedder for generating embeddings
            
        Returns:
            Dictionary with processing results
        """
        try:
            print(f"🔄 Starting MDL processing workflow for project: {project_id}")
            
            # Step 1: Append definitions to existing MDL
            print("🔄 Step 1: Appending definitions to MDL...")
            updated_mdl = MDLSchemaGenerator.append_definitions_to_mdl_from_context(
                existing_mdl=existing_mdl,
                definitions=definitions,
                project_context=project_context,
                project_id=project_id
            )
            print(f"✅ Appended {len(definitions)} definitions to MDL")
            
            # Step 2: Validate the updated MDL
            print("🔄 Step 2: Validating updated MDL...")
            is_valid, errors = MDLSchemaGenerator.validate_mdl_schema(updated_mdl)
            if not is_valid:
                print(f"❌ MDL validation failed with {len(errors)} errors:")
                for error in errors[:5]:
                    print(f"  - {error}")
                return {
                    "success": False,
                    "error": f"MDL validation failed: {errors[0] if errors else 'Unknown error'}",
                    "project_id": project_id
                }
            print("✅ MDL validation passed")
            
            # Step 3: Process with table_description.py for storage
            print("🔄 Step 3: Processing with table_description.py...")
            from app.agents.indexing.table_description import TableDescription
            
            table_processor = TableDescription(
                document_store=table_doc_store,
                embedder=embedder
            )
            
            # Convert MDL to JSON string for processing
            import json
            mdl_json = json.dumps(updated_mdl, indent=2)
            
            # Process the MDL
            result = await table_processor.run(mdl_json, project_id=project_id)
            print(f"✅ TableDescription processed {result.get('documents_written', 0)} documents")
            
            # Step 4: Optional: Process with schema_manager.py for enhanced documentation
            print("🔄 Step 4: Processing with schema_manager.py...")
            try:
                from app.agents.schema_manager import SchemaDocumentationUtils
                
                # Create a documented table from the MDL for enhanced processing
                # This would require converting MDL back to DocumentedTable format
                # For now, we'll just note that this integration is possible
                print("✅ Schema manager integration available")
                
            except ImportError:
                print("⚠️ Schema manager not available, skipping enhanced documentation")
            
            return {
                "success": True,
                "documents_written": result.get('documents_written', 0),
                "project_id": project_id,
                "mdl_models": len(updated_mdl.get("models", [])),
                "mdl_views": len(updated_mdl.get("views", [])),
                "mdl_metrics": len(updated_mdl.get("metrics", [])),
                "definitions_appended": len(definitions),
                "processing_method": "mdl_append_with_table_description"
            }
            
        except Exception as e:
            print(f"❌ Error in MDL processing workflow: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id
            }
    
    @staticmethod
    def create_sample_mdl_for_demo() -> Dict[str, Any]:
        """
        Create a sample MDL for demonstration purposes
        This simulates an existing MDL that would be passed to the utility
        """
        return {
            "catalog": "ecommerce_catalog",
            "schema": "public",
            "models": [
                {
                    "name": "users",
                    "baseObject": "users",
                    "columns": [
                        {
                            "name": "user_id",
                            "type": "INTEGER",
                            "notNull": True,
                            "properties": {
                                "description": "Unique user identifier",
                                "display_name": "User ID"
                            }
                        },
                        {
                            "name": "email",
                            "type": "VARCHAR",
                            "notNull": True,
                            "properties": {
                                "description": "User email address",
                                "display_name": "Email"
                            }
                        }
                    ],
                    "properties": {
                        "description": "User account information",
                        "display_name": "Users"
                    }
                }
            ],
            "views": [],
            "relationships": [],
            "metrics": [
                {
                    "name": "total_users",
                    "baseObject": "users",
                    "dimension": [],
                    "measure": [
                        {
                            "name": "total_users",
                            "type": "INTEGER",
                            "properties": {
                                "description": "Count of all users",
                                "display_name": "Total Users"
                            }
                        }
                    ],
                    "properties": {
                        "description": "Total number of users",
                        "display_name": "Total Users"
                    }
                }
            ],
            "cumulativeMetrics": [],
            "enumDefinitions": []
        }


# ============================================================================
# EXAMPLE USAGE AND DEMONSTRATION
# ============================================================================

class DefinitionGenerationExamples:
    """Example usage of the LLM Definition Generator service"""
    
    @staticmethod
    def ecommerce_project_example():
        """Example for E-commerce project with comprehensive context"""
        
        # Sample project context
        context = {
            "tables": {
                "users": {
                    "name": "users",
                    "description": "User account information and profiles",
                    "columns": [
                        {"name": "user_id", "type": "INTEGER", "description": "Unique user identifier"},
                        {"name": "email", "type": "VARCHAR", "description": "User email address"},
                        {"name": "first_name", "type": "VARCHAR", "description": "User first name"},
                        {"name": "last_name", "type": "VARCHAR", "description": "User last name"},
                        {"name": "created_at", "type": "TIMESTAMP", "description": "Account creation date"},
                        {"name": "status", "type": "VARCHAR", "description": "Account status (active, inactive, suspended)"},
                        {"name": "registration_source", "type": "VARCHAR", "description": "How user registered (web, mobile, referral)"}
                    ]
                },
                "orders": {
                    "name": "orders",
                    "description": "Customer order information and details",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "description": "Unique order identifier"},
                        {"name": "user_id", "type": "INTEGER", "description": "User who placed the order"},
                        {"name": "order_date", "type": "TIMESTAMP", "description": "Order placement date and time"},
                        {"name": "total_amount", "type": "DECIMAL", "description": "Total order amount including tax and shipping"},
                        {"name": "subtotal", "type": "DECIMAL", "description": "Order subtotal before tax and shipping"},
                        {"name": "tax_amount", "type": "DECIMAL", "description": "Tax amount for the order"},
                        {"name": "shipping_amount", "type": "DECIMAL", "description": "Shipping cost for the order"},
                        {"name": "status", "type": "VARCHAR", "description": "Order status (pending, confirmed, shipped, delivered, cancelled)"},
                        {"name": "payment_method", "type": "VARCHAR", "description": "Payment method used (credit_card, paypal, etc.)"}
                    ]
                },
                "order_items": {
                    "name": "order_items",
                    "description": "Individual items within each order",
                    "columns": [
                        {"name": "order_item_id", "type": "INTEGER", "description": "Unique order item identifier"},
                        {"name": "order_id", "type": "INTEGER", "description": "Order this item belongs to"},
                        {"name": "product_id", "type": "INTEGER", "description": "Product identifier"},
                        {"name": "quantity", "type": "INTEGER", "description": "Quantity of product ordered"},
                        {"name": "unit_price", "type": "DECIMAL", "description": "Price per unit at time of order"},
                        {"name": "total_price", "type": "DECIMAL", "description": "Total price for this item (quantity * unit_price)"}
                    ]
                },
                "products": {
                    "name": "products",
                    "description": "Product catalog information",
                    "columns": [
                        {"name": "product_id", "type": "INTEGER", "description": "Unique product identifier"},
                        {"name": "name", "type": "VARCHAR", "description": "Product name"},
                        {"name": "description", "type": "TEXT", "description": "Product description"},
                        {"name": "category", "type": "VARCHAR", "description": "Product category"},
                        {"name": "brand", "type": "VARCHAR", "description": "Product brand"},
                        {"name": "price", "type": "DECIMAL", "description": "Current product price"},
                        {"name": "cost", "type": "DECIMAL", "description": "Product cost for margin calculation"},
                        {"name": "inventory_quantity", "type": "INTEGER", "description": "Available inventory quantity"},
                        {"name": "is_active", "type": "BOOLEAN", "description": "Whether product is active for sale"}
                    ]
                },
                "reviews": {
                    "name": "reviews",
                    "description": "Customer product reviews and ratings",
                    "columns": [
                        {"name": "review_id", "type": "INTEGER", "description": "Unique review identifier"},
                        {"name": "product_id", "type": "INTEGER", "description": "Product being reviewed"},
                        {"name": "user_id", "type": "INTEGER", "description": "User who wrote the review"},
                        {"name": "rating", "type": "INTEGER", "description": "Rating from 1-5 stars"},
                        {"name": "review_text", "type": "TEXT", "description": "Review text content"},
                        {"name": "review_date", "type": "TIMESTAMP", "description": "Date review was written"},
                        {"name": "is_verified_purchase", "type": "BOOLEAN", "description": "Whether reviewer purchased the product"}
                    ]
                }
            },
            "existing_metrics": {
                "total_users": "Count of all registered users",
                "total_orders": "Count of all orders placed",
                "total_revenue": "Sum of all order amounts",
                "average_order_value": "Average amount per order"
            },
            "business_context": {
                "domain": "E-commerce",
                "key_metrics": ["revenue", "conversion_rate", "customer_lifetime_value", "average_order_value", "customer_satisfaction"],
                "business_goals": ["increase_sales", "improve_customer_satisfaction", "reduce_customer_churn", "optimize_inventory"],
                "kpi_focus": ["monthly_recurring_revenue", "customer_acquisition_cost", "customer_retention_rate"],
                "analytics_needs": ["customer_segmentation", "product_performance", "sales_trends", "inventory_optimization"]
            },
            "data_lineage": {
                "orders": ["users", "order_items"],
                "order_items": ["orders", "products"],
                "reviews": ["users", "products"]
            }
        }
        
        # Example user examples for different definition types
        user_examples = {
            "conversion_rate": UserExample(
                definition_type=DefinitionType.METRIC,
                name="conversion_rate",
                description="Calculate the percentage of users who made a purchase",
                sql="SELECT COUNT(DISTINCT o.user_id) * 100.0 / COUNT(DISTINCT u.user_id) FROM users u LEFT JOIN orders o ON u.user_id = o.user_id",
                additional_context={"business_goal": "measure_user_engagement", "target": "increase_conversion"}
            ),
            "customer_lifetime_value": UserExample(
                definition_type=DefinitionType.METRIC,
                name="customer_lifetime_value",
                description="Calculate average total revenue per customer",
                sql="SELECT AVG(total_spent) FROM (SELECT u.user_id, SUM(o.total_amount) as total_spent FROM users u LEFT JOIN orders o ON u.user_id = o.user_id GROUP BY u.user_id)",
                additional_context={"business_goal": "customer_valuation", "use_case": "marketing_budget_allocation"}
            ),
            "user_order_summary": UserExample(
                definition_type=DefinitionType.VIEW,
                name="user_order_summary",
                description="Create a view showing user order statistics for reporting",
                sql="SELECT u.user_id, u.email, COUNT(o.order_id) as order_count, SUM(o.total_amount) as total_spent, AVG(o.total_amount) as avg_order_value FROM users u LEFT JOIN orders o ON u.user_id = o.user_id GROUP BY u.user_id, u.email",
                additional_context={"purpose": "reporting_and_analytics", "audience": "business_analysts"}
            ),
            "product_performance": UserExample(
                definition_type=DefinitionType.VIEW,
                name="product_performance",
                description="Create a view showing product performance metrics",
                sql="SELECT p.product_id, p.name, p.category, COUNT(oi.order_item_id) as units_sold, SUM(oi.total_price) as revenue, AVG(r.rating) as avg_rating FROM products p LEFT JOIN order_items oi ON p.product_id = oi.product_id LEFT JOIN reviews r ON p.product_id = r.product_id GROUP BY p.product_id, p.name, p.category",
                additional_context={"purpose": "product_analysis", "audience": "product_managers"}
            ),
            "order_value_tier": UserExample(
                definition_type=DefinitionType.CALCULATED_COLUMN,
                name="order_value_tier",
                description="Categorize orders into value tiers based on total amount",
                sql="CASE WHEN total_amount >= 200 THEN 'High Value' WHEN total_amount >= 100 THEN 'Medium Value' ELSE 'Low Value' END",
                additional_context={"business_rule": "segment_customers_by_spending", "use_case": "customer_segmentation"}
            ),
            "profit_margin": UserExample(
                definition_type=DefinitionType.CALCULATED_COLUMN,
                name="profit_margin",
                description="Calculate profit margin percentage for products",
                sql="CASE WHEN cost > 0 THEN ROUND(((price - cost) / cost) * 100, 2) ELSE 0 END",
                additional_context={"business_rule": "margin_calculation", "use_case": "pricing_analysis"}
            ),
            "customer_satisfaction_score": UserExample(
                definition_type=DefinitionType.METRIC,
                name="customer_satisfaction_score",
                description="Calculate average customer satisfaction score from reviews",
                sql="SELECT AVG(rating) FROM reviews WHERE is_verified_purchase = true",
                additional_context={"business_goal": "measure_customer_satisfaction", "quality_filter": "verified_purchases_only"}
            )
        }
        
        return context, user_examples
    
    @staticmethod
    def financial_services_example():
        """Example for Financial Services project with regulatory context"""
        
        context = {
            "tables": {
                "customers": {
                    "name": "customers",
                    "description": "Customer information and KYC data",
                    "columns": [
                        {"name": "customer_id", "type": "INTEGER", "description": "Unique customer identifier"},
                        {"name": "ssn", "type": "VARCHAR", "description": "Social Security Number (encrypted)"},
                        {"name": "first_name", "type": "VARCHAR", "description": "Customer first name"},
                        {"name": "last_name", "type": "VARCHAR", "description": "Customer last name"},
                        {"name": "date_of_birth", "type": "DATE", "description": "Customer date of birth"},
                        {"name": "risk_profile", "type": "VARCHAR", "description": "Risk assessment profile (low, medium, high)"},
                        {"name": "kyc_status", "type": "VARCHAR", "description": "KYC verification status"},
                        {"name": "account_opened_date", "type": "TIMESTAMP", "description": "Date account was opened"}
                    ]
                },
                "transactions": {
                    "name": "transactions",
                    "description": "Financial transaction records",
                    "columns": [
                        {"name": "transaction_id", "type": "INTEGER", "description": "Unique transaction identifier"},
                        {"name": "customer_id", "type": "INTEGER", "description": "Customer who made the transaction"},
                        {"name": "transaction_date", "type": "TIMESTAMP", "description": "Transaction date and time"},
                        {"name": "amount", "type": "DECIMAL", "description": "Transaction amount (positive for credits, negative for debits)"},
                        {"name": "transaction_type", "type": "VARCHAR", "description": "Type of transaction (deposit, withdrawal, transfer, payment)"},
                        {"name": "category", "type": "VARCHAR", "description": "Transaction category (groceries, utilities, entertainment, etc.)"},
                        {"name": "merchant_name", "type": "VARCHAR", "description": "Merchant or counterparty name"},
                        {"name": "is_suspicious", "type": "BOOLEAN", "description": "Flag for suspicious activity detection"}
                    ]
                },
                "accounts": {
                    "name": "accounts",
                    "description": "Customer account information",
                    "columns": [
                        {"name": "account_id", "type": "INTEGER", "description": "Unique account identifier"},
                        {"name": "customer_id", "type": "INTEGER", "description": "Customer who owns the account"},
                        {"name": "account_type", "type": "VARCHAR", "description": "Account type (checking, savings, credit, investment)"},
                        {"name": "balance", "type": "DECIMAL", "description": "Current account balance"},
                        {"name": "credit_limit", "type": "DECIMAL", "description": "Credit limit for credit accounts"},
                        {"name": "interest_rate", "type": "DECIMAL", "description": "Interest rate for the account"},
                        {"name": "status", "type": "VARCHAR", "description": "Account status (active, inactive, frozen, closed)"}
                    ]
                }
            },
            "business_context": {
                "domain": "Financial Services",
                "key_metrics": ["customer_lifetime_value", "churn_rate", "acquisition_cost", "fraud_detection_rate"],
                "business_goals": ["increase_retention", "reduce_churn", "optimize_acquisition", "prevent_fraud"],
                "regulatory_requirements": ["GDPR", "SOX", "PCI_DSS", "AML", "KYC"],
                "risk_factors": ["credit_risk", "operational_risk", "compliance_risk", "fraud_risk"]
            }
        }
        
        user_examples = {
            "fraud_detection_rate": UserExample(
                definition_type=DefinitionType.METRIC,
                name="fraud_detection_rate",
                description="Calculate percentage of transactions flagged as suspicious",
                sql="SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM transactions) FROM transactions WHERE is_suspicious = true",
                additional_context={"business_goal": "fraud_prevention", "regulatory": "AML_compliance"}
            ),
            "customer_risk_profile": UserExample(
                definition_type=DefinitionType.CALCULATED_COLUMN,
                name="customer_risk_profile",
                description="Calculate customer risk score based on transaction patterns",
                sql="CASE WHEN COUNT(CASE WHEN is_suspicious = true THEN 1 END) > 5 THEN 'High Risk' WHEN COUNT(CASE WHEN is_suspicious = true THEN 1 END) > 2 THEN 'Medium Risk' ELSE 'Low Risk' END",
                additional_context={"business_rule": "risk_assessment", "regulatory": "AML_requirements"}
            )
        }
        
        return context, user_examples


async def demo_llm_definition_generation(definition_generator: LLMDefinitionGenerator):
    """Demonstrate LLM Definition Generator service"""
    
    print("🚀 LLM Definition Generator Service Demo")
    print("=" * 60)
    
    # Get example data
    context, user_examples = DefinitionGenerationExamples.ecommerce_project_example()
    
    print("\n📋 Project Context:")
    print(f"  Domain: {context['business_context']['domain']}")
    print(f"  Key Metrics: {', '.join(context['business_context']['key_metrics'])}")
    print(f"  Business Goals: {', '.join(context['business_context']['business_goals'])}")
    print(f"  Available Tables: {', '.join(context['tables'].keys())}")
    
    # Test all three definition types
    definition_types = {
        "Metrics": [user_examples["conversion_rate"], user_examples["customer_lifetime_value"], user_examples["customer_satisfaction_score"]],
        "Views": [user_examples["user_order_summary"], user_examples["product_performance"]],
        "Calculated Columns": [user_examples["order_value_tier"], user_examples["profit_margin"]]
    }
    
    results = {}
    
    for definition_type, examples in definition_types.items():
        print(f"\n📊 {definition_type} Generation:")
        print("-" * 40)
        
        results[definition_type] = []
        
        for i, example in enumerate(examples, 1):
            print(f"\n  {i}. Generating {example.name}...")
            
            try:
                if example.definition_type == DefinitionType.METRIC:
                    result = await definition_generator.generate_metric_definition(example, context)
                elif example.definition_type == DefinitionType.VIEW:
                    result = await definition_generator.generate_view_definition(example, context)
                else:  # CALCULATED_COLUMN
                    result = await definition_generator.generate_calculated_column_definition(example, context)
                
                results[definition_type].append(result)
                
                print(f"    ✅ Generated: {result.display_name}")
                print(f"    📝 Description: {result.description[:100]}...")
                print(f"    🎯 Confidence: {result.confidence_score:.2f}")
                print(f"    🔗 Related Tables: {', '.join(result.related_tables)}")
                print(f"    💡 Suggestions: {len(result.suggestions)} suggestions")
                
                # Show enhanced SQL if it's different from original
                if result.sql_query != example.sql:
                    print(f"    🔧 Enhanced SQL: {result.sql_query[:100]}...")
                
            except Exception as e:
                print(f"    ❌ Error generating {example.name}: {str(e)}")
                results[definition_type].append(None)
    
    # Summary and validation
    print(f"\n📈 Generation Summary:")
    print("=" * 40)
    
    total_generated = 0
    total_successful = 0
    
    for definition_type, results_list in results.items():
        successful = len([r for r in results_list if r is not None])
        total = len(results_list)
        total_generated += total
        total_successful += successful
        
        print(f"  {definition_type}: {successful}/{total} successful")
    
    print(f"\n  Overall Success Rate: {total_successful}/{total_generated} ({total_successful/total_generated*100:.1f}%)")
    
    # Show detailed examples
    print(f"\n🔍 Detailed Examples:")
    print("=" * 40)
    
    # Show one successful example from each type
    for definition_type, results_list in results.items():
        successful_results = [r for r in results_list if r is not None]
        if successful_results:
            example = successful_results[0]
            print(f"\n📋 {definition_type} Example - {example.display_name}:")
            print(f"  Name: {example.name}")
            print(f"  Description: {example.description}")
            print(f"  SQL Query: {example.sql_query}")
            print(f"  Chain of Thought: {example.chain_of_thought[:200]}...")
            print(f"  Related Tables: {example.related_tables}")
            print(f"  Related Columns: {example.related_columns}")
            print(f"  Confidence Score: {example.confidence_score}")
            print(f"  Metadata: {list(example.metadata.keys())}")
            print(f"  Suggestions: {example.suggestions}")
    
    # Demonstrate validation
    print(f"\n🔍 Validation Demo:")
    print("=" * 40)
    
    # Create a mock validation service for demo
    class MockValidationService:
        def validate_definition(self, definition):
            # Simulate validation
            errors = []
            if definition.confidence_score < 0.8:
                errors.append(f"Low confidence score: {definition.confidence_score}")
            if not definition.related_tables:
                errors.append("No related tables specified")
            if not definition.sql_query:
                errors.append("No SQL query provided")
            
            return len(errors) == 0, errors
    
    validator = MockValidationService()
    
    for definition_type, results_list in results.items():
        successful_results = [r for r in results_list if r is not None]
        if successful_results:
            example = successful_results[0]
            is_valid, errors = validator.validate_definition(example)
            
            print(f"\n  {definition_type} - {example.display_name}:")
            if is_valid:
                print(f"    ✅ Valid")
            else:
                print(f"    ❌ Validation Errors:")
                for error in errors:
                    print(f"      - {error}")
    
    # Demonstrate business value
    print(f"\n💼 Business Value Demonstration:")
    print("=" * 40)
    
    print("  🎯 Generated definitions provide:")
    print("    - Enhanced business-friendly names and descriptions")
    print("    - Optimized SQL queries with proper formatting")
    print("    - Detailed chain of thought explanations")
    print("    - Related tables and columns for data lineage")
    print("    - Comprehensive metadata for governance")
    print("    - Confidence scores for quality assessment")
    print("    - Actionable suggestions for improvement")
    
    print(f"\n  📊 Key Benefits:")
    print("    - Faster definition creation (automated vs manual)")
    print("    - Consistent quality and formatting")
    print("    - Business context awareness")
    print("    - Regulatory compliance considerations")
    print("    - Performance optimization suggestions")
    
    print(f"\n✅ Demo completed successfully!")
    print(f"Generated {total_successful} enhanced definitions across {len(definition_types)} types")
    
    # Demonstrate MDL schema generation
    print(f"\n🔧 MDL Schema Generation Demo:")
    print("=" * 40)
    
    # Collect all successful results
    all_definitions = []
    for results_list in results.values():
        all_definitions.extend([r for r in results_list if r is not None])
    
    if all_definitions:
        print(f"  📊 Appending {len(all_definitions)} definitions to MDL schema...")
        
        # Create initial MDL from project context
        initial_mdl = MDLSchemaGenerator.create_initial_mdl_from_context(
            project_context=context,
            project_id="ecommerce_demo"
        )
        
        # Append definitions to the existing MDL
        updated_mdl = MDLSchemaGenerator.append_definitions_to_mdl_from_context(
            existing_mdl=initial_mdl,
            definitions=all_definitions,
            project_context=context,
            project_id="ecommerce_demo"
        )
        
        # Validate the schema
        is_valid, errors = MDLSchemaGenerator.validate_mdl_schema(updated_mdl)
        
        print(f"  ✅ MDL Schema generated successfully!")
        print(f"  📋 Schema Summary:")
        print(f"    - Catalog: {updated_mdl['catalog']}")
        print(f"    - Schema: {updated_mdl['schema']}")
        print(f"    - Models: {len(updated_mdl['models'])}")
        print(f"    - Views: {len(updated_mdl['views'])}")
        print(f"    - Metrics: {len(updated_mdl['metrics'])}")
        print(f"    - Relationships: {len(updated_mdl['relationships'])}")
        
        if is_valid:
            print(f"  ✅ Schema validation passed")
        else:
            print(f"  ❌ Schema validation failed:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"    - {error}")
        
        # Show example MDL structure
        print(f"\n  📄 Example MDL Structure:")
        if updated_mdl['metrics']:
            metric_example = updated_mdl['metrics'][0]
            print(f"    Metric: {metric_example['name']}")
            print(f"      - Base Object: {metric_example['baseObject']}")
            print(f"      - Dimensions: {len(metric_example['dimension'])}")
            print(f"      - Measures: {len(metric_example['measure'])}")
            print(f"      - Properties: {list(metric_example['properties'].keys())}")
        
        if updated_mdl['views']:
            view_example = updated_mdl['views'][0]
            print(f"    View: {view_example['name']}")
            print(f"      - Statement: {view_example['statement'][:100]}...")
            print(f"      - Properties: {list(view_example['properties'].keys())}")
        
        if updated_mdl['models']:
            model_example = updated_mdl['models'][0]
            print(f"    Model: {model_example['name']}")
            print(f"      - Base Object: {model_example['baseObject']}")
            print(f"      - Columns: {len(model_example['columns'])}")
            print(f"      - Properties: {list(model_example['properties'].keys())}")
        
        # Demonstrate integration with existing MDL and table_description.py
        print(f"\n  🔗 Integration with existing MDL and table_description.py:")
        print(f"    - Appends definitions to existing MDL schema")
        print(f"    - Calculated columns are added to appropriate models")
        print(f"    - Metrics and views are added to their respective arrays")
        print(f"    - MDL can be processed by TableDescription class for storage")
        print(f"    - Enables semantic search across all definition types")
        
        # Show example of appending to existing MDL
        print(f"\n  📋 Example: Appending to existing MDL:")
        sample_mdl = MDLSchemaGenerator.create_sample_mdl_for_demo()
        print(f"    - Existing MDL has {len(sample_mdl['models'])} models")
        print(f"    - Existing MDL has {len(sample_mdl['metrics'])} metrics")
        
        # Simulate appending definitions to existing MDL
        updated_sample_mdl = MDLSchemaGenerator.append_definitions_to_mdl(
            existing_mdl=sample_mdl,
            definitions=all_definitions[:2],  # Just first 2 for demo
            project_id="ecommerce_demo"
        )
        
        print(f"    - After appending: {len(updated_sample_mdl['models'])} models")
        print(f"    - After appending: {len(updated_sample_mdl['metrics'])} metrics")
        print(f"    - After appending: {len(updated_sample_mdl['views'])} views")
        
        # Show calculated column integration
        calculated_columns_added = 0
        for model in updated_sample_mdl['models']:
            for column in model.get('columns', []):
                if column.get('isCalculated', False):
                    calculated_columns_added += 1
        
        print(f"    - Calculated columns added: {calculated_columns_added}")
        
        # Show the complete MDL JSON (first 500 chars)
        import json
        mdl_json = json.dumps(updated_mdl, indent=2)
        print(f"\n  📋 Complete MDL JSON (first 500 chars):")
        print(f"    {mdl_json[:500]}...")
        
    else:
        print(f"  ❌ No successful definitions to generate MDL schema from")


async def demo_complete_workflow_integration():
    """Demonstrate complete workflow integration with schema_manager.py and table_description.py"""
    
    print("🚀 Complete Workflow Integration Demo")
    print("=" * 60)
    
    # Get example data
    context, user_examples = DefinitionGenerationExamples.ecommerce_project_example()
    
    # Initialize LLM and generator
    llm = get_llm()
    definition_generator = LLMDefinitionGenerator(llm)
    
    print("\n📋 Step 1: Generate LLM Definitions")
    print("-" * 40)
    
    # Generate a few definitions for demo
    definitions = []
    example_examples = [
        user_examples["conversion_rate"],
        user_examples["user_order_summary"],
        user_examples["order_value_tier"]
    ]
    
    for i, example in enumerate(example_examples, 1):
        print(f"  {i}. Generating {example.name}...")
        try:
            if example.definition_type == DefinitionType.METRIC:
                result = await definition_generator.generate_metric_definition(example, context)
            elif example.definition_type == DefinitionType.VIEW:
                result = await definition_generator.generate_view_definition(example, context)
            else:  # CALCULATED_COLUMN
                result = await definition_generator.generate_calculated_column_definition(example, context)
            
            definitions.append(result)
            print(f"    ✅ Generated: {result.display_name}")
            
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
    
    if not definitions:
        print("❌ No definitions generated, cannot continue demo")
        return
    
    print(f"\n✅ Generated {len(definitions)} definitions")
    
    print("\n📋 Step 2: Create/Get Existing MDL")
    print("-" * 40)
    
    # Simulate existing MDL (in real usage, this would come from schema_manager.py)
    existing_mdl = MDLSchemaGenerator.create_sample_mdl_for_demo()
    print(f"  📊 Existing MDL contains:")
    print(f"    - {len(existing_mdl['models'])} models")
    print(f"    - {len(existing_mdl['metrics'])} metrics")
    print(f"    - {len(existing_mdl['views'])} views")
    
    print("\n📋 Step 3: Append Definitions to MDL")
    print("-" * 40)
    
    # Append definitions to existing MDL
    updated_mdl = MDLSchemaGenerator.append_definitions_to_mdl_from_context(
        existing_mdl=existing_mdl,
        definitions=definitions,
        project_context=context,
        project_id="ecommerce_demo"
    )
    
    print(f"  📊 Updated MDL contains:")
    print(f"    - {len(updated_mdl['models'])} models")
    print(f"    - {len(updated_mdl['metrics'])} metrics")
    print(f"    - {len(updated_mdl['views'])} views")
    
    # Show what was added
    new_metrics = len(updated_mdl['metrics']) - len(existing_mdl['metrics'])
    new_views = len(updated_mdl['views']) - len(existing_mdl['views'])
    print(f"  ➕ Added: {new_metrics} metrics, {new_views} views")
    
    # Count calculated columns added
    calculated_columns_added = 0
    for model in updated_mdl['models']:
        for column in model.get('columns', []):
            if column.get('isCalculated', False):
                calculated_columns_added += 1
    
    print(f"  ➕ Calculated columns: {calculated_columns_added}")
    
    print("\n📋 Step 4: Validate MDL")
    print("-" * 40)
    
    is_valid, errors = MDLSchemaGenerator.validate_mdl_schema(updated_mdl)
    if is_valid:
        print("  ✅ MDL validation passed")
    else:
        print(f"  ❌ MDL validation failed with {len(errors)} errors:")
        for error in errors[:3]:
            print(f"    - {error}")
    
    print("\n📋 Step 5: Process with table_description.py")
    print("-" * 40)
    
    try:
        # Initialize document store and embedder for demo
        from app.storage.documents import DocumentChromaStore
        import chromadb
        from langchain_openai import OpenAIEmbeddings
        from app.core.settings import get_settings
        
        settings = get_settings()
        
        print("  🔧 Initializing ChromaDB and embeddings...")
        persistent_client = chromadb.PersistentClient(path="./chroma_db")
        table_doc_store = DocumentChromaStore(
            persistent_client=persistent_client,
            collection_name="table_description_demo"
        )
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Process with table_description.py
        print("  🔄 Processing MDL with TableDescription...")
        from app.agents.indexing.table_description import TableDescription
        
        table_processor = TableDescription(
            document_store=table_doc_store,
            embedder=embeddings
        )
        
        import json
        mdl_json = json.dumps(updated_mdl, indent=2)
        
        result = await table_processor.run(mdl_json, project_id="ecommerce_demo")
        print(f"  ✅ TableDescription processed {result.get('documents_written', 0)} documents")
        
        # Show what was stored
        print(f"  📊 Storage Summary:")
        print(f"    - Models stored: {len(updated_mdl['models'])}")
        print(f"    - Views stored: {len(updated_mdl['views'])}")
        print(f"    - Metrics stored: {len(updated_mdl['metrics'])}")
        print(f"    - Total documents: {result.get('documents_written', 0)}")
        
    except Exception as e:
        print(f"  ❌ TableDescription processing failed: {e}")
        print("  ⚠️ This is expected if ChromaDB or embeddings are not configured")
    
    print("\n📋 Step 6: Integration with schema_manager.py")
    print("-" * 40)
    
    print("  🔗 Integration Points:")
    print("    - MDLSchemaGenerator.append_definitions_to_mdl() can be called from schema_manager.py")
    print("    - Existing MDL from schema_manager.py can be passed to this utility")
    print("    - Generated definitions are appended to existing schema")
    print("    - Updated MDL can be stored back to schema_manager.py")
    
    print("\n📋 Step 7: Complete Workflow Summary")
    print("-" * 40)
    
    print("  🔄 Complete Workflow:")
    print("    1. schema_manager.py generates initial MDL from project context")
    print("    2. LLMDefinitionGenerator creates enhanced definitions")
    print("    3. MDLSchemaGenerator.append_definitions_to_mdl() merges them")
    print("    4. table_description.py processes and stores the updated MDL")
    print("    5. ChromaDB indexes all definitions for semantic search")
    
    print("\n  💡 Key Benefits:")
    print("    - Non-destructive: Appends to existing MDL, doesn't replace")
    print("    - Incremental: Can add definitions over time")
    print("    - Integrated: Works with existing schema_manager.py workflow")
    print("    - Searchable: All definitions indexed in ChromaDB")
    print("    - Validated: MDL schema validation ensures quality")
    
    print("\n✅ Complete workflow integration demo finished!")
    print(f"Successfully demonstrated integration between:")
    print(f"  - LLMDefinitionGenerator (project_manager.py)")
    print(f"  - MDLSchemaGenerator (project_manager.py)")
    print(f"  - schema_manager.py")
    print(f"  - table_description.py")


if __name__ == "__main__":
    from app.core.settings import init_environment
    init_environment()
    
    try:
        # Run the complete workflow integration demo
        asyncio.run(asyncio.wait_for(demo_complete_workflow_integration(), timeout=300.0))
    except asyncio.TimeoutError:
        print("❌ Demo timed out after 300 seconds")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()





