"""
LLM-Powered Schema Documentation Service
Automatically generates intelligent column descriptions, usage patterns, and examples
from schema definitions and project context.

This service generates MDL (Model Definition Language) JSON structures that are processed
by db_schema.py, which handles the helper utilities for preprocessing and comment generation.
The workflow is:
1. Generate schema documentation using LLM
2. Convert to MDL format (matching data/sql_meta/cornerstone/mdl.json structure)
3. Process MDL with db_schema.py (which uses helper utilities internally)
4. Store in ChromaDB with proper formatting
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
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langchain_openai import ChatOpenAI

# Import our models
from app.schemas.dbmodels import (
    Project, Table
)

from app.service.models import (
    ProjectContext, SchemaInput, DocumentedTable, EnhancedColumnDefinition, ColumnDocumentationSchema, ColumnUsageType
)
from app.core.dependencies import get_llm

# Import the existing helper utility from db_schema
from app.agents.indexing.db_schema import DBSchema
from app.agents.indexing.table_description import TableDescription

# ============================================================================
# LLM SCHEMA DOCUMENTATION GENERATOR
# ============================================================================

class LLMSchemaDocumentationGenerator:
    """LLM-powered generator for schema documentation"""
    
    def __init__(self, llm=None):
        self.client = llm or get_llm()
        
    
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
        ***Important: Return the response as a JSON object with the keys specified above. and do not include any json tags or other separations. If not the responses will fail***
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
        # print("Raw LLM Response:")
        print(response)
        # print("=" * 50)
        
        try:
            # Try to parse the response as JSON
            parsed_response = json.loads(response)
            print("Successfully parsed JSON response")
            return parsed_response
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            print("Attempting to extract JSON from response...")
            
            # Try to extract JSON from the response if it's wrapped in markdown or other text
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    extracted_json = json_match.group(0)
                    parsed_response = json.loads(extracted_json)
                    print("Successfully extracted and parsed JSON")
                    return parsed_response
                except json.JSONDecodeError as e2:
                    print(f"Extracted JSON parsing also failed: {e2}")
            
            # If all else fails, return a default structure
            print("Returning default response structure")
            return {
                "display_name": schema_input.table_name,
                "description": f"Table {schema_input.table_name}",
                "business_purpose": "Business purpose not generated",
                "primary_use_cases": ["Use case analysis needed"],
                "key_relationships": ["Relationship analysis needed"],
                "data_lineage": "Data lineage not specified",
                "update_frequency": "unknown",
                "data_retention": "Data retention not specified",
                "access_patterns": ["Access pattern analysis needed"],
                "performance_considerations": ["Performance analysis needed"]
            }
    
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
            {sample_values}
            ***Important: Return the response as a JSON object with the keys specified above. and do not include any json tags or other separations. If not the responses will fail***
            """)
        ])
        
        # Create the chain
        chain = (
            prompt 
            | self.client 
            | parser
        )

        
        # Prepare the input
        # Handle both 'data_type' and 'type' keys for column type
        data_type = column.get('data_type') or column.get('type', 'UNKNOWN')
        
        chain_input = {
            "format_instructions": parser.get_format_instructions(),
            "column_name": column['name'],
            "data_type": data_type,
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
                data_type=data_type,
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
        """Format columns for LLM prompt using the existing helper utility"""
        formatted = []
        for col in columns:
            # Handle both 'data_type' and 'type' keys for column type
            data_type = col.get('data_type') or col.get('type', 'UNKNOWN')
            col_info = f"- {col['name']} ({data_type})"
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
            print("Calling LLM...")
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
            
            # Execute the chain with timeout
            import asyncio
            response = await asyncio.wait_for(chain.ainvoke(formattedInputs), timeout=60.0)
            print("LLM call completed successfully")
            return response
            
        except asyncio.TimeoutError:
            print("LLM call timed out after 60 seconds")
            raise Exception("LLM call timed out")
        except Exception as e:
            print(f"LLM call failed: {str(e)}")
            raise Exception(f"LLM call failed: {str(e)}")


class SchemaDocumentationUtils:
    """Utility methods for schema documentation using existing helper utilities"""
    
    @staticmethod
    def documented_table_to_mdl(documented_table: DocumentedTable, project_id: str) -> str:
        """
        Convert a DocumentedTable to MDL (Model Definition Language) format
        that can be processed by DBSchema for ChromaDB storage.
        Generates the proper MDL structure that db_schema.py will process.
        
        Args:
            documented_table: The documented table object
            project_id: The project identifier
            
        Returns:
            JSON string in MDL format
        """
        # Convert columns to MDL format - no preprocessing here, let db_schema handle it
        mdl_columns = []
        for column in documented_table.columns:
            # Create column dict in the standard MDL format
            mdl_column = {
                "name": column.column_name,
                "type": column.data_type,
                "properties": {
                    "displayName": column.display_name,
                    "description": column.description,
                    "businessDescription": column.business_description,
                    "usageType": column.usage_type.value,
                    "exampleValues": column.example_values,
                    "businessRules": column.business_rules,
                    "dataQualityChecks": column.data_quality_checks,
                    "relatedConcepts": column.related_concepts,
                    "privacyClassification": column.privacy_classification,
                    "aggregationSuggestions": column.aggregation_suggestions,
                    "filteringSuggestions": column.filtering_suggestions,
                    "metadata": column.metadata
                }
            }
            
            # Add calculated field properties if applicable
            if column.metadata.get("isCalculated", False):
                mdl_column["isCalculated"] = True
                mdl_column["expression"] = column.metadata.get("expression", "")
            
            mdl_columns.append(mdl_column)
        
        # Create the model definition in MDL format
        model = {
            "name": documented_table.table_name,
            "description": documented_table.description,
            "columns": mdl_columns,
            "primaryKey": None,  # Will be set if we have primary key information
            "properties": {
                "displayName": documented_table.display_name,
                "description": documented_table.description,
                "businessPurpose": documented_table.business_purpose,
                "primaryUseCases": documented_table.primary_use_cases,
                "keyRelationships": documented_table.key_relationships,
                "dataLineage": documented_table.data_lineage,
                "updateFrequency": documented_table.update_frequency,
                "dataRetention": documented_table.data_retention,
                "accessPatterns": documented_table.access_patterns,
                "performanceConsiderations": documented_table.performance_considerations,
                "projectId": project_id
            }
        }
        
        # Try to identify primary key from column metadata
        for column in documented_table.columns:
            if column.metadata.get("is_primary_key", False):
                model["primaryKey"] = column.column_name
                break
        
        # Create the complete MDL structure matching the format in mdl.json
        mdl = {
            "catalog": f"{project_id}_catalog",
            "schema": "public",
            "models": [model],
            "views": [],
            "relationships": [],
            "metrics": [],
            "cumulativeMetrics": [],
            "enumDefinitions": []
        }
        
        return json.dumps(mdl, indent=2)
    
    @staticmethod
    def documented_table_to_chroma_documents(documented_table: DocumentedTable, project_id: str) -> List[Dict[str, Any]]:
        """
        Convert a DocumentedTable to ChromaDB document format for direct storage.
        This method is now simplified - the actual processing will be done by db_schema.py
        which will handle the helper utilities and comment generation.
        
        Args:
            documented_table: The documented table object
            project_id: The project identifier
            
        Returns:
            List of document dictionaries ready for ChromaDB storage
        """
        import uuid
        from langchain_core.documents import Document as LangchainDocument
        
        documents = []
        
        # Create table-level document
        table_doc = {
            "id": str(uuid.uuid4()),
            "metadata": {
                "type": "TABLE_SCHEMA",
                "name": documented_table.table_name,
                "project_id": project_id,
                "documentation_type": "table_overview"
            },
            "page_content": json.dumps({
                "type": "TABLE",
                "name": documented_table.table_name,
                "display_name": documented_table.display_name,
                "description": documented_table.description,
                "business_purpose": documented_table.business_purpose,
                "primary_use_cases": documented_table.primary_use_cases,
                "key_relationships": documented_table.key_relationships,
                "data_lineage": documented_table.data_lineage,
                "update_frequency": documented_table.update_frequency,
                "data_retention": documented_table.data_retention,
                "access_patterns": documented_table.access_patterns,
                "performance_considerations": documented_table.performance_considerations
            }, indent=2)
        }
        documents.append(LangchainDocument(**table_doc))
        
        # Create column-level documents - simplified, let db_schema handle the details
        for column in documented_table.columns:
            column_doc = {
                "id": str(uuid.uuid4()),
                "metadata": {
                    "type": "TABLE_SCHEMA",
                    "name": f"{documented_table.table_name}.{column.column_name}",
                    "project_id": project_id,
                    "table_name": documented_table.table_name,
                    "column_name": column.column_name,
                    "documentation_type": "column_detail"
                },
                "page_content": json.dumps({
                    "type": "COLUMN",
                    "table_name": documented_table.table_name,
                    "name": column.column_name,
                    "display_name": column.display_name,
                    "data_type": column.data_type,
                    "description": column.description,
                    "business_description": column.business_description,
                    "usage_type": column.usage_type.value,
                    "example_values": column.example_values,
                    "business_rules": column.business_rules,
                    "data_quality_checks": column.data_quality_checks,
                    "related_concepts": column.related_concepts,
                    "privacy_classification": column.privacy_classification,
                    "aggregation_suggestions": column.aggregation_suggestions,
                    "filtering_suggestions": column.filtering_suggestions,
                    "metadata": column.metadata
                    # Note: Comments will be generated by db_schema.py helper utilities
                }, indent=2)
            }
            documents.append(LangchainDocument(**column_doc))
        
        return documents
    
    @staticmethod
    async def process_and_store_schema(
        documented_table: DocumentedTable,
        project_context: ProjectContext,
        document_store: Any,
        table_doc_store: Any,
        embedder: Any = None
    ) -> Dict[str, Any]:
        """
        Complete workflow: Process documented table and store in ChromaDB.
        Uses MDL format and db_schema.py for processing with helper utilities.
        
        Args:
            documented_table: The documented table object
            project_context: The project context
            document_store: ChromaDB document store instance
            embedder: Optional embedder for generating embeddings
            
        Returns:
            Dictionary with processing results
        """
        try:
   
            
            # Step 2: Convert to MDL format
            print("🔄 Step 2: Converting to MDL format...")
            mdl_json = SchemaDocumentationUtils.documented_table_to_mdl(documented_table, project_context.project_id)
            print("✅ MDL format generated")
            
            # Step 3: Process MDL using db_schema.py (which handles helper utilities)
            print("🔄 Step 3: Processing MDL with db_schema.py...")
            
            db_schema = DBSchema(
                document_store=document_store,
                embedder=embedder
            )
            """
            # Process the MDL - this will use the helper utilities internally
            result = await db_schema.run(mdl_json, project_id=project_context.project_id)
            print(f"✅ DBSchema processed {result.get('documents_written', 0)} documents using helper utilities")
            """
            table_description = TableDescription(
                document_store=table_doc_store,
                embedder=embedder
            )
            
            result = await table_description.run(mdl_json, project_id=project_context.project_id)
            print(f"✅ TableDescription processed {result.get('documents_written', 0)} documents using helper utilities")
            
            return {
                "success": True,
                "documents_written": result.get('documents_written', 0),
                "project_id": project_context.project_id,
                "table_name": documented_table.table_name,
                "documented_table": documented_table,
                "mdl_json": mdl_json,
                "processing_method": "db_schema_with_helpers"
            }
            
        except Exception as e:
            print(f"❌ Error in process_and_store_schema: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "project_id": project_context.project_id
            }

    @staticmethod
    async def process_schema_input_and_store(
        schema_input: SchemaInput,
        project_context: ProjectContext,
        document_store: Any,
        embedder: Any = None,
        llm: Any = None
    ) -> Dict[str, Any]:
        """
        Complete workflow: Generate schema documentation from input and store in ChromaDB.
        This is a convenience method that combines documentation generation and storage.
        
        Args:
            schema_input: The schema input data
            project_context: The project context
            document_store: ChromaDB document store instance
            embedder: Optional embedder for generating embeddings
            llm: Optional LLM instance for documentation generation
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Step 1: Generate schema documentation
            print("🔄 Step 1: Generating schema documentation...")
            schema_manager = LLMSchemaDocumentationGenerator(llm)
            documented_table = await schema_manager.document_table_schema(schema_input, project_context)
            print("✅ Schema documentation generated")
            
            # Step 2: Process and store using the documented table
            return await SchemaDocumentationUtils.process_and_store_schema(
                documented_table=documented_table,
                project_context=project_context,
                document_store=document_store,
                embedder=embedder
            )
            
        except Exception as e:
            print(f"❌ Error in process_schema_input_and_store: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "project_id": project_context.project_id
            }


class SchemaDocumentationExamples:
    """Example usage of the schema documentation service"""
    
    @staticmethod
    def cornerstone_training_example():
        """Example for Cornerstone training project"""
        
        project_context = ProjectContext(
            project_id="cornerstone",
            project_name="Cornerstone Training Analysis",
            business_domain="training_management",
            purpose="Track and analyze employee training completion, compliance, and performance across the organization",
            target_users=["HR Analysts", "Training Coordinators", "Managers", "Executives"],
            key_business_concepts=[
                "training_completion", "compliance", "performance_tracking", 
                "manager_oversight", "division_analysis", "timeliness"
            ],
            data_sources=["Cornerstone OnDemand", "HR Systems", "Employee Database"],
            compliance_requirements=["SOX", "GDPR", "Training Compliance Audits"]
        )
        
        # Example DDL for training records table
        ddl_statement = """
        CREATE TABLE csod_training_records (
            User_ID VARCHAR(50) NOT NULL,
            Division VARCHAR(100),
            Position VARCHAR(100),
            Manager_Name VARCHAR(200),
            Training_Title VARCHAR(500),
            Training_Type VARCHAR(100),
            Transcript_Status VARCHAR(50),
            Assigned_Date DATETIME,
            Due_Date DATETIME,
            Completed_Date DATETIME,
            PRIMARY KEY (User_ID, Training_Title, Assigned_Date)
        );
        """
        
        # Example JSON schema with sample data
        schema_json = {
            "table_name": "csod_training_records",
            "description": "Training records from Cornerstone OnDemand system",
            "columns": [
                {"name": "User_ID", "type": "VARCHAR(50)", "nullable": False, "primary_key": True},
                {"name": "Division", "type": "VARCHAR(100)", "nullable": True},
                {"name": "Position", "type": "VARCHAR(100)", "nullable": True},
                {"name": "Manager_Name", "type": "VARCHAR(200)", "nullable": True},
                {"name": "Training_Title", "type": "VARCHAR(500)", "nullable": False},
                {"name": "Training_Type", "type": "VARCHAR(100)", "nullable": True},
                {"name": "Transcript_Status", "type": "VARCHAR(50)", "nullable": False},
                {"name": "Assigned_Date", "type": "DATETIME", "nullable": False},
                {"name": "Due_Date", "type": "DATETIME", "nullable": True},
                {"name": "Completed_Date", "type": "DATETIME", "nullable": True}
            ],
            "sample_data": [
                {
                    "User_ID": "EMP001",
                    "Division": "Administration",
                    "Position": "Manager",
                    "Manager_Name": "John Smith",
                    "Training_Title": "Data Privacy and Security",
                    "Training_Type": "Compliance Course",
                    "Transcript_Status": "Satisfied",
                    "Assigned_Date": "2024-01-15",
                    "Due_Date": "2024-02-15",
                    "Completed_Date": "2024-02-10"
                },
                {
                    "User_ID": "EMP002",
                    "Division": "Acme Products",
                    "Position": "Analyst",
                    "Manager_Name": "Jane Doe",
                    "Training_Title": "Excel Advanced Functions",
                    "Training_Type": "Skills Development",
                    "Transcript_Status": "Assigned",
                    "Assigned_Date": "2024-02-01",
                    "Due_Date": "2024-03-01",
                    "Completed_Date": None
                }
            ]
        }
        
        return project_context, ddl_statement, schema_json


async def demo_schema_documentation(schema_manager: LLMSchemaDocumentationGenerator):
    """Demonstrate schema documentation service"""
    
    # This would be initialized with actual database session and API key
    # session = get_database_session()
    # service = SchemaDocumentationService(
    #     session=session,
    #     openai_api_key="your-api-key",
    #     project_id="cornerstone"
    # )
    
    # Get example data
    project_context, ddl_statement, schema_json = (
        SchemaDocumentationExamples.cornerstone_training_example()
    )
    
    print("🚀 Schema Documentation Service Demo")
    print("=" * 50)
    
    print("\n📋 Project Context:")
    print(f"  Domain: {project_context.business_domain}")
    print(f"  Purpose: {project_context.purpose}")
    print(f"  Users: {', '.join(project_context.target_users)}")
    print(f"  Key Concepts: {', '.join(project_context.key_business_concepts)}")
    
    # Example 1: Document from DDL
    print(f"\n📊 Example 1: Document from DDL")
    print(f"DDL Statement: {ddl_statement[:100]}...")
    # documented_table = await service.document_schema_from_ddl(ddl_statement, project_context)
    
    # Example 2: Document from JSON with sample data
    print(f"\n📋 Example 2: Document from JSON with sample data")
    print(f"Sample data includes {len(schema_json['sample_data'])} rows")
    
    # Convert dictionary to SchemaInput object
    schema_input = SchemaInput(
        table_name=schema_json['table_name'],
        table_description=schema_json.get('description'),
        columns=schema_json['columns'],
        sample_data=schema_json.get('sample_data')
    )
    
    # Example 3: Batch document all project tables
    print(f"\n🔄 Example 3: Batch document all tables in project")
    # documented_tables = await service.batch_document_project_tables(project_context)
    
    print("\n✅ Documentation complete!")
    print("Generated documentation includes:")
    print("  - Business-friendly column names")
    print("  - Detailed descriptions and usage patterns")
    print("  - Example values and business rules")
    print("  - Data quality checks and privacy classifications")
    print("  - Aggregation and filtering suggestions")
    
    print("\n🔄 Starting schema documentation generation...")
    try:
        documented_table = await schema_manager.document_table_schema(schema_input, project_context)
        print("✅ Schema documentation generated successfully!")
        print(documented_table)
        
        # Demonstrate utility methods
        print("\n🔄 Converting to MDL format...")
        mdl_json = SchemaDocumentationUtils.documented_table_to_mdl(documented_table, project_context.project_id)
        print("✅ MDL format generated:")
        #print(mdl_json)

        
        print("\n🔄 Converting to ChromaDB documents...")
        chroma_documents = SchemaDocumentationUtils.documented_table_to_chroma_documents(documented_table, project_context.project_id)
        print(f"✅ Generated {len(chroma_documents)} ChromaDB documents")
        
        # Show example of first document
        """
        if chroma_documents:
            print("\n📄 Example ChromaDB document:")
            print(f"Metadata: {chroma_documents[0].metadata}")
            print(f"Content preview: {chroma_documents[0].page_content[:200]}...")
        """

        # Demonstrate MDL-based approach with db_schema.py
        print("\n🔄 Demonstrating MDL-based approach with db_schema.py...")
        print("  - MDL structure generated matches the format in data/sql_meta/cornerstone/mdl.json")
        print("  - db_schema.py will handle:")
        print("    * Column preprocessing using COLUMN_PREPROCESSORS")
        print("    * Comment generation using COLUMN_COMMENT_HELPERS")
        print("    * Properties handling with _properties_comment")
        print("    * DDL command generation and document creation")
        
        # Show example of the MDL structure
        print("\n📄 Example MDL structure generated:")
        print(f"  - Catalog: {project_context.project_id}_catalog")
        print(f"  - Schema: public")
        print(f"  - Model: {documented_table.table_name}")
        print(f"  - Columns: {len(documented_table.columns)}")
        print(f"  - Primary Key: {next((col.column_name for col in documented_table.columns if col.metadata.get('is_primary_key')), 'None')}")
        
        # Demonstrate the complete workflow with document store
        print("\n🔄 Demonstrating complete workflow with document store...")
        try:
            # Initialize document store and embedder for demo
            from app.storage.documents import DocumentChromaStore
            import chromadb
            from langchain_openai import OpenAIEmbeddings
            from app.core.settings import get_settings
            
            settings = get_settings()
            
            # Initialize ChromaDB and embeddings
            print("  - Initializing ChromaDB and embeddings...")
            persistent_client = chromadb.PersistentClient(path="./chroma_db")
            doc_store = DocumentChromaStore(
                persistent_client=persistent_client,
                collection_name="schema_documentation"
            )
            table_doc_store = DocumentChromaStore(
                persistent_client=persistent_client,
                collection_name="table_description"
            )
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=settings.OPENAI_API_KEY
            )
            
            # Method 1: Step-by-step approach (using already generated documented_table)
            print("\n  📋 Method 1: Step-by-step approach")
            output1 = await SchemaDocumentationUtils.process_and_store_schema(
                documented_table=documented_table,
                project_context=project_context,
                document_store=doc_store,
                table_doc_store=table_doc_store,
                embedder=embeddings
            )
            #print(f"    - Step-by-step result: {output1}")

            """ 
            # Method 2: Convenience method approach (from schema input)
            print("\n  📋 Method 2: Convenience method approach")
            output2 = await SchemaDocumentationUtils.process_schema_input_and_store(
                schema_input=schema_input,
                project_context=project_context,
                document_store=doc_store,
                embedder=embeddings,
                llm=schema_manager.client
            )
            print(f"    - Convenience method result: {output2}")
            """
        except Exception as e:
            print(f"  - Document store demo failed: {e}")
            print("  - This is expected if ChromaDB or embeddings are not configured")
        
        # Demonstrate the workflow
        print("\n🔄 Workflow demonstration:")
        print("  1. Schema documentation generated ✅")
        print("  2. MDL JSON structure created ✅")
        print("  3. db_schema.py processes MDL with helper utilities")
        print("  4. ChromaDB documents created with proper formatting")
        
        # Show a sample of the MDL JSON
        print(f"\n📋 Sample MDL JSON (first 200 chars):")
        print(f"  {mdl_json[:200]}...")
        
    except Exception as e:
        print(f"❌ Error generating schema documentation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    from app.core.settings import init_environment
    init_environment()
    llm = get_llm()
    schema_manager = LLMSchemaDocumentationGenerator(llm)
    
    try:
        # Run with a timeout
        asyncio.run(asyncio.wait_for(demo_schema_documentation(schema_manager), timeout=120.0))
    except asyncio.TimeoutError:
        print("❌ Demo timed out after 120 seconds")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    


