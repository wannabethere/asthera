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
from fastapi import HTTPException
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

# Import our models
from app.service.dbmodels import (
    Project, Table, Columns, Metric, View, CalculatedColumn, 
    determine_change_type
)
from app.service.projectManagerService import ProjectManager
from app.service.models import UserExample,GeneratedDefinition,DefinitionType
import traceback

class TableMatchingTool(BaseTool):
    """Langchain tool for matching user descriptions to actual tables and columns"""
    
    name: str = "table_matching"
    description: str = "Matches user descriptions to actual database tables and columns"
    session: Any
    project_id: str
    
    # def __init__(self, session: Session, project_id: str):
    #     super().__init__()
    #     self.session = session
    #     self.project_id = project_id
    
    def _run(self, description: str) -> str:
        """Find matching tables and columns for a description"""
        # Get all tables and columns for the project
        tables = self.session.query(Table).filter(Table.project_id == self.project_id).all()
        
        matches = []
        for table in tables:
            # Simple keyword matching - in production, use semantic similarity
            if any(keyword in description.lower() for keyword in [
                table.name.lower(), 
                table.display_name.lower() if table.display_name else "",
                table.description.lower() if table.description else ""
            ]):
                table_info = {
                    "table_name": table.name,
                    "table_description": table.description,
                    "columns": []
                }
                
                for column in table.columns:
                    if any(keyword in description.lower() for keyword in [
                        column.name.lower(),
                        column.display_name.lower() if column.display_name else "",
                        column.description.lower() if column.description else ""
                    ]):
                        table_info["columns"].append({
                            "name": column.name,
                            "type": column.data_type,
                            "description": column.description
                        })
                
                matches.append(table_info)
        
        return json.dumps(matches)
    
    async def _arun(self, description: str) -> str:
        """Async version of _run"""
        return self._run(description)


class LLMDefinitionGenerator:
    """LLM-powered generator for creating enhanced definitions"""
    
    def __init__(self, openai_api_key: str, model: str = "gpt-4"):
        self.client = ChatOpenAI(api_key=openai_api_key, model=model)
        self.model = model
    
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
        
        Return a JSON response with the following structure:
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
        
        Return a JSON response with the following structure:
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
        
        Return a JSON response with the following structure:
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
            
            # We raise a generic error to the client, but the real error is in our logs.
            raise HTTPException(status_code=500, detail="An internal error occurred. Check server logs for full traceback.")

    
    def _parse_response(self, response: str, definition_type: DefinitionType) -> GeneratedDefinition:
        """Parse LLM response into GeneratedDefinition"""
        try:
            data = json.loads(response)
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
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse LLM response: {str(e)}")


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





