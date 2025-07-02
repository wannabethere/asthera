"""
LLM-Powered Schema Documentation Service
Automatically generates intelligent column descriptions, usage patterns, and examples
from schema definitions and project context
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import re
from datetime import datetime

import openai
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.pydantic_v1 import BaseModel as PydanticBaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.pydantic_v1 import BaseModel as PydanticBaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langchain_openai import ChatOpenAI

# Import our models
from app.service.dbmodels import (
    Project, Table, Columns
)
from app.service.models import (
    ProjectContext,SchemaInput,DocumentedTable,EnhancedColumnDefinition,ColumnDocumentationSchema
)




# ============================================================================
# SCHEMA PARSING UTILITIES
# ============================================================================

class SchemaParser:
    """Parse various schema formats into standardized format"""
    
    @staticmethod
    def parse_ddl(ddl_statement: str) -> SchemaInput:
        """Parse DDL CREATE TABLE statement"""
        # Simple DDL parser - in production, use a proper SQL parser
        table_name_match = re.search(r'CREATE TABLE\s+(\w+)', ddl_statement, re.IGNORECASE)
        table_name = table_name_match.group(1) if table_name_match else "unknown_table"
        
        # Extract column definitions
        columns = []
        column_pattern = r'(\w+)\s+([A-Z]+(?:\(\d+(?:,\s*\d+)?\))?)[^,\n]*'
        
        for match in re.finditer(column_pattern, ddl_statement):
            column_name = match.group(1)
            data_type = match.group(2)
            
            # Skip common SQL keywords
            if column_name.upper() in ['PRIMARY', 'FOREIGN', 'KEY', 'CONSTRAINT', 'REFERENCES']:
                continue
                
            columns.append({
                "name": column_name,
                "data_type": data_type,
                "nullable": "NOT NULL" not in match.group(0).upper(),
                "primary_key": "PRIMARY KEY" in match.group(0).upper()
            })
        
        return SchemaInput(
            table_name=table_name,
            table_description=None,
            columns=columns
        )
    
    @staticmethod
    def parse_sqlalchemy_table(table: Table) -> SchemaInput:
        """Parse SQLAlchemy table model"""
        columns = []
        for column in table.columns:
            columns.append({
                "name": column.name,
                "data_type": str(column.data_type) if column.data_type else "VARCHAR",
                "nullable": column.is_nullable,
                "primary_key": column.is_primary_key,
                "description": column.description
            })
        
        return SchemaInput(
            table_name=table.name,
            table_description=table.description,
            columns=columns
        )
    
    @staticmethod
    def parse_json_schema(schema_json: Dict[str, Any]) -> SchemaInput:
        """Parse JSON schema definition"""
        table_name = schema_json.get("table_name", "unknown_table")
        columns = []
        
        for col_def in schema_json.get("columns", []):
            columns.append({
                "name": col_def.get("name"),
                "data_type": col_def.get("type", "VARCHAR"),
                "nullable": col_def.get("nullable", True),
                "primary_key": col_def.get("primary_key", False),
                "description": col_def.get("description")
            })
        
        return SchemaInput(
            table_name=table_name,
            table_description=schema_json.get("description"),
            columns=columns,
            sample_data=schema_json.get("sample_data"),
            constraints=schema_json.get("constraints")
        )


# ============================================================================
# LLM SCHEMA DOCUMENTATION GENERATOR
# ============================================================================

class LLMSchemaDocumentationGenerator:
    """LLM-powered generator for schema documentation"""
    
    def __init__(self, openai_api_key: str, model: str = "gpt-4"):
        self.client = ChatOpenAI(api_key=openai_api_key, model=model)
        self.model = model
    
    async def document_table_schema(self, schema_input: SchemaInput, 
                                  project_context: ProjectContext) -> DocumentedTable:
        """Generate comprehensive table documentation"""
        
        # Generate table-level documentation
        table_doc = await self._generate_table_documentation(schema_input, project_context)
        
        # Generate column-level documentation
        column_docs = []
        for column in schema_input.columns:
            column_doc = await self._generate_column_documentation(
                column, schema_input, project_context
            )
            column_docs.append(column_doc)
        
        return DocumentedTable(
            table_name=schema_input.table_name,
            display_name=table_doc["display_name"],
            description=table_doc["description"],
            business_purpose=table_doc["business_purpose"],
            primary_use_cases=table_doc["primary_use_cases"],
            key_relationships=table_doc["key_relationships"],
            columns=column_docs,
            data_lineage=table_doc.get("data_lineage"),
            update_frequency=table_doc["update_frequency"],
            data_retention=table_doc.get("data_retention"),
            access_patterns=table_doc["access_patterns"],
            performance_considerations=table_doc["performance_considerations"]
        )
    
    async def _generate_table_documentation(self, schema_input: SchemaInput, 
                                          project_context: ProjectContext) -> Dict[str, Any]:
        """Generate table-level documentation"""
        
        system_prompt = """You are an expert data architect and business analyst. 
        Generate comprehensive table documentation that bridges technical schema details 
        with business context. Focus on:
        1. Clear business purpose and value
        2. Primary use cases and access patterns
        3. Relationships to business processes
        4. Data governance considerations
        """
        
        user_prompt ="""
        Document this database table for business users and analysts:
        
        Table Information:
        - Name: {name}
        - Description: {description}
        - Columns: {columns} columns
        
        Column Overview:
        {columnOverview}
        
        Project Context:
        - Domain: {domain}
        - Purpose: {purpose}
        - Target Users: {target_users}
        - Key Concepts: {key_business_concepts}
        
        Sample Data (if available):
        {sample_data}
        
        Generate a JSON response with:
        {{
            "display_name": "Business-friendly table name",
            "description": "Clear, comprehensive table description for business users",
            "business_purpose": "Why this table exists and its business value",
            "primary_use_cases": ["use_case1", "use_case2", "use_case3"],
            "key_relationships": ["relationship1", "relationship2"],
            "data_lineage": "Where this data comes from and how it's populated",
            "update_frequency": "real-time|hourly|daily|weekly|monthly",
            "data_retention": "How long data is kept",
            "access_patterns": ["pattern1", "pattern2"],
            "performance_considerations": ["consideration1", "consideration2"]
        }}
        """
        formattedInputs ={
            "name": schema_input.table_name,
            "description": schema_input.table_description if schema_input.table_description else "Not provided",
            "columns": len(schema_input.columns) if schema_input.columns else 0,
            "columnOverview": self._format_columns_for_prompt(schema_input.columns),
            "domain": project_context.business_domain,
            "purpose": project_context.purpose,
            "target_users": ','.join(project_context.target_users),
            "key_business_concepts": ','.join(project_context.key_business_concepts),
            "sample_data": json.dumps(schema_input.sample_data[:3] if schema_input.sample_data else [], indent=2)
        } 
        
        response = await self._call_llm(system_prompt, user_prompt, formattedInputs)
        return json.loads(response)
    
    async def _generate_column_documentation(self, column: Dict[str, Any], 
                                           schema_input: SchemaInput,
                                           project_context: ProjectContext) -> EnhancedColumnDefinition:
        """Generate enhanced column documentation using Langchain prompt template"""
        
        # Create the output parser
        parser = PydanticOutputParser(pydantic_object=ColumnDocumentationSchema)
        
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert data analyst specializing in data dictionary creation.
            Generate comprehensive column documentation that helps business users understand:
            1. What the column represents in business terms
            2. How it should be used in analysis
            3. Data quality and business rules
            4. Privacy and compliance considerations
            
            Be specific and actionable in your recommendations.
            
            {format_instructions}"""),
            ("human", """Document this database column for business analysis:
            
            Column Details:
            - Name: {column_name}
            - Data Type: {data_type}
            - Nullable: {nullable}
            - Primary Key: {primary_key}
            - Existing Description: {existing_description}
            
            Table Context:
            - Table: {table_name}
            - Other Columns: {other_columns}
            
            Project Context:
            - Business Domain: {business_domain}
            - Purpose: {purpose}
            - Key Concepts: {key_concepts}
            - Compliance: {compliance}
            
            Sample Values (if available):
            {sample_values}""")
        ])
        
        # Create the chain
        chain = (
            prompt 
            | self.client 
            | parser
        )
        
        # Prepare the input
        chain_input = {
            "format_instructions": parser.get_format_instructions(),
            "column_name": column['name'],
            "data_type": column['data_type'],
            "nullable": column.get('nullable', True),
            "primary_key": column.get('primary_key', False),
            "existing_description": column.get('description', 'None'),
            "table_name": schema_input.table_name,
            "other_columns": [c['name'] for c in schema_input.columns if c['name'] != column['name']],
            "business_domain": project_context.business_domain,
            "purpose": project_context.purpose,
            "key_concepts": ', '.join(project_context.key_business_concepts),
            "compliance": ', '.join(project_context.compliance_requirements or []),
            "sample_values": self._extract_sample_values_for_column(column['name'], schema_input.sample_data)
        }
        
        # Execute the chain
        try:
            data = await chain.ainvoke(chain_input)
            
            return EnhancedColumnDefinition(
                column_name=column['name'],
                display_name=data.display_name,
                description=data.description,
                business_description=data.business_description,
                usage_type=ColumnUsageType(data.usage_type),
                data_type=column['data_type'],
                example_values=data.example_values,
                business_rules=data.business_rules,
                data_quality_checks=data.data_quality_checks,
                related_concepts=data.related_concepts,
                privacy_classification=data.privacy_classification,
                aggregation_suggestions=data.aggregation_suggestions,
                filtering_suggestions=data.filtering_suggestions,
                metadata=data.metadata
            )
        except Exception as e:
            raise Exception(f"Failed to generate column documentation: {str(e)}")
    
    def _format_columns_for_prompt(self, columns: List[Dict[str, Any]]) -> str:
        """Format columns for LLM prompt"""
        formatted = []
        for col in columns:
            col_info = f"- {col['name']} ({col['data_type']})"
            if col.get('primary_key'):
                col_info += " [PRIMARY KEY]"
            if not col.get('nullable', True):
                col_info += " [NOT NULL]"
            if col.get('description'):
                col_info += f" - {col['description']}"
            formatted.append(col_info)
        return '\n'.join(formatted)
    
    def _extract_sample_values_for_column(self, column_name: str, 
                                        sample_data: Optional[List[Dict[str, Any]]]) -> str:
        """Extract sample values for a specific column"""
        if not sample_data:
            return "No sample data available"
        
        values = []
        for row in sample_data:
            if column_name in row and row[column_name] is not None:
                values.append(str(row[column_name]))
        
        if values:
            return f"Sample values: {', '.join(values[:5])}"
        return "No sample values found"
    
    async def _call_llm(self, system_prompt: str, user_prompt: str, formattedInputs: Dict[str, Any]) -> str:
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
            
            # Execute the chain
            response = await chain.ainvoke(formattedInputs)
            return response
            
        except Exception as e:
            raise Exception(f"LLM call failed: {str(e)}")







