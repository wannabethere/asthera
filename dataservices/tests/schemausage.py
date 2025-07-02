"""
LLM-Powered Schema Documentation Service
Automatically generates intelligent column descriptions, usage patterns, and examples
from schema definitions and project context
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re
from datetime import datetime

import openai
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from pydantic import BaseModel, Field

# Import our models
from sqlalchemy_models import (
    Project, Table, Column, ProjectManager
)


# ============================================================================
# DATA MODELS
# ============================================================================

class ColumnUsageType(Enum):
    """Types of column usage in business context"""
    DIMENSION = "dimension"          # Categorical data for grouping/filtering
    MEASURE = "measure"             # Numeric data for aggregation
    ATTRIBUTE = "attribute"         # Descriptive information
    IDENTIFIER = "identifier"       # Unique identifiers
    TIMESTAMP = "timestamp"         # Date/time information
    FLAG = "flag"                  # Boolean indicators
    METADATA = "metadata"          # System/technical information
    CALCULATED = "calculated"      # Derived/computed values


@dataclass
class SchemaInput:
    """Input schema information"""
    table_name: str
    table_description: Optional[str]
    columns: List[Dict[str, Any]]  # Raw column definitions
    sample_data: Optional[List[Dict[str, Any]]] = None
    constraints: Optional[List[Dict[str, Any]]] = None


@dataclass
class ProjectContext:
    """Business context for schema documentation"""
    project_id: str
    project_name: str
    business_domain: str
    purpose: str
    target_users: List[str]
    key_business_concepts: List[str]
    data_sources: Optional[List[str]] = None
    compliance_requirements: Optional[List[str]] = None


@dataclass
class EnhancedColumnDefinition:
    """Enhanced column definition with LLM-generated insights"""
    column_name: str
    display_name: str
    description: str
    business_description: str
    usage_type: ColumnUsageType
    data_type: str
    example_values: List[str]
    business_rules: List[str]
    data_quality_checks: List[str]
    related_concepts: List[str]
    privacy_classification: str
    aggregation_suggestions: List[str]
    filtering_suggestions: List[str]
    metadata: Dict[str, Any]


@dataclass
class DocumentedTable:
    """Complete table documentation"""
    table_name: str
    display_name: str
    description: str
    business_purpose: str
    primary_use_cases: List[str]
    key_relationships: List[str]
    columns: List[EnhancedColumnDefinition]
    data_lineage: Optional[str]
    update_frequency: str
    data_retention: Optional[str]
    access_patterns: List[str]
    performance_considerations: List[str]


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
        self.client = openai.OpenAI(api_key=openai_api_key)
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
        
        user_prompt = f"""
        Document this database table for business users and analysts:
        
        Table Information:
        - Name: {schema_input.table_name}
        - Description: {schema_input.table_description or 'Not provided'}
        - Columns: {len(schema_input.columns)} columns
        
        Column Overview:
        {self._format_columns_for_prompt(schema_input.columns)}
        
        Project Context:
        - Domain: {project_context.business_domain}
        - Purpose: {project_context.purpose}
        - Target Users: {', '.join(project_context.target_users)}
        - Key Concepts: {', '.join(project_context.key_business_concepts)}
        
        Sample Data (if available):
        {json.dumps(schema_input.sample_data[:3] if schema_input.sample_data else [], indent=2)}
        
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
        
        response = await self._call_llm(system_prompt, user_prompt)
        return json.loads(response)
    
    async def _generate_column_documentation(self, column: Dict[str, Any], 
                                           schema_input: SchemaInput,
                                           project_context: ProjectContext) -> EnhancedColumnDefinition:
        """Generate enhanced column documentation"""
        
        system_prompt = """You are an expert data analyst specializing in data dictionary creation.
        Generate comprehensive column documentation that helps business users understand:
        1. What the column represents in business terms
        2. How it should be used in analysis
        3. Data quality and business rules
        4. Privacy and compliance considerations
        
        Be specific and actionable in your recommendations."""
        
        user_prompt = f"""
        Document this database column for business analysis:
        
        Column Details:
        - Name: {column['name']}
        - Data Type: {column['data_type']}
        - Nullable: {column.get('nullable', True)}
        - Primary Key: {column.get('primary_key', False)}
        - Existing Description: {column.get('description', 'None')}
        
        Table Context:
        - Table: {schema_input.table_name}
        - Other Columns: {[c['name'] for c in schema_input.columns if c['name'] != column['name']]}
        
        Project Context:
        - Business Domain: {project_context.business_domain}
        - Purpose: {project_context.purpose}
        - Key Concepts: {', '.join(project_context.key_business_concepts)}
        - Compliance: {', '.join(project_context.compliance_requirements or [])}
        
        Sample Values (if available):
        {self._extract_sample_values_for_column(column['name'], schema_input.sample_data)}
        
        Generate a JSON response with:
        {{
            "display_name": "Business-friendly column name",
            "description": "Technical description for developers",
            "business_description": "Business description for analysts and managers",
            "usage_type": "dimension|measure|attribute|identifier|timestamp|flag|metadata|calculated",
            "example_values": ["example1", "example2", "example3"],
            "business_rules": ["rule1", "rule2"],
            "data_quality_checks": ["check1", "check2"],
            "related_concepts": ["concept1", "concept2"],
            "privacy_classification": "public|internal|confidential|restricted",
            "aggregation_suggestions": ["COUNT", "SUM", "AVG"] or [],
            "filtering_suggestions": ["common_filter1", "common_filter2"],
            "metadata": {{
                "typical_cardinality": "high|medium|low",
                "common_patterns": ["pattern1", "pattern2"],
                "business_importance": "critical|important|supporting",
                "analysis_frequency": "daily|weekly|monthly|rarely"
            }}
        }}
        """
        
        response = await self._call_llm(system_prompt, user_prompt)
        data = json.loads(response)
        
        return EnhancedColumnDefinition(
            column_name=column['name'],
            display_name=data['display_name'],
            description=data['description'],
            business_description=data['business_description'],
            usage_type=ColumnUsageType(data['usage_type']),
            data_type=column['data_type'],
            example_values=data['example_values'],
            business_rules=data['business_rules'],
            data_quality_checks=data['data_quality_checks'],
            related_concepts=data['related_concepts'],
            privacy_classification=data['privacy_classification'],
            aggregation_suggestions=data['aggregation_suggestions'],
            filtering_suggestions=data['filtering_suggestions'],
            metadata=data['metadata']
        )
    
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
    
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM with prompts and return response"""
        try:
            response = await self.client.chat.completions.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"LLM call failed: {str(e)}")


# ============================================================================
# SCHEMA DOCUMENTATION SERVICE
# ============================================================================

class SchemaDocumentationService:
    """Main service for schema documentation"""
    
    def __init__(self, session: Session, openai_api_key: str, project_id: str):
        self.session = session
        self.project_id = project_id
        self.project_manager = ProjectManager(session)
        self.llm_generator = LLMSchemaDocumentationGenerator(openai_api_key)
        self.schema_parser = SchemaParser()
    
    async def document_schema_from_ddl(self, ddl_statement: str, 
                                     project_context: ProjectContext) -> DocumentedTable:
        """Document schema from DDL statement"""
        schema_input = self.schema_parser.parse_ddl(ddl_statement)
        return await self.llm_generator.document_table_schema(schema_input, project_context)
    
    async def document_existing_table(self, table_name: str, 
                                    project_context: ProjectContext,
                                    include_sample_data: bool = False) -> DocumentedTable:
        """Document existing table in database"""
        # Get table from database
        table = self.session.query(Table).filter(
            Table.project_id == self.project_id,
            Table.name == table_name
        ).first()
        
        if not table:
            raise ValueError(f"Table {table_name} not found in project {self.project_id}")
        
        # Convert to schema input
        schema_input = self.schema_parser.parse_sqlalchemy_table(table)
        
        # Optionally include sample data
        if include_sample_data:
            schema_input.sample_data = await self._get_sample_data(table_name)
        
        return await self.llm_generator.document_table_schema(schema_input, project_context)
    
    async def document_schema_from_json(self, schema_json: Dict[str, Any],
                                      project_context: ProjectContext) -> DocumentedTable:
        """Document schema from JSON definition"""
        schema_input = self.schema_parser.parse_json_schema(schema_json)
        return await self.llm_generator.document_table_schema(schema_input, project_context)
    
    async def batch_document_project_tables(self, project_context: ProjectContext,
                                          table_names: Optional[List[str]] = None) -> List[DocumentedTable]:
        """Document all or specified tables in a project"""
        # Get tables to document
        query = self.session.query(Table).filter(Table.project_id == self.project_id)
        if table_names:
            query = query.filter(Table.name.in_(table_names))
        
        tables = query.all()
        
        if not tables:
            raise ValueError(f"No tables found in project {self.project_id}")
        
        # Document each table
        documented_tables = []
        for table in tables:
            try:
                schema_input = self.schema_parser.parse_sqlalchemy_table(table)
                documented_table = await self.llm_generator.document_table_schema(
                    schema_input, project_context
                )
                documented_tables.append(documented_table)
            except Exception as e:
                print(f"Warning: Failed to document table {table.name}: {str(e)}")
        
        return documented_tables
    
    async def update_database_with_documentation(self, documented_table: DocumentedTable) -> bool:
        """Update database with generated documentation"""
        try:
            # Update table documentation
            table = self.session.query(Table).filter(
                Table.project_id == self.project_id,
                Table.name == documented_table.table_name
            ).first()
            
            if not table:
                return False
            
            table.display_name = documented_table.display_name
            table.description = documented_table.description
            table.metadata = {
                **(table.metadata or {}),
                'business_purpose': documented_table.business_purpose,
                'primary_use_cases': documented_table.primary_use_cases,
                'key_relationships': documented_table.key_relationships,
                'data_lineage': documented_table.data_lineage,
                'update_frequency': documented_table.update_frequency,
                'data_retention': documented_table.data_retention,
                'access_patterns': documented_table.access_patterns,
                'performance_considerations': documented_table.performance_considerations,
                'documentation_generated_at': datetime.utcnow().isoformat(),
                'documentation_source': 'llm_schema_service'
            }
            
            # Update column documentation
            for col_doc in documented_table.columns:
                column = self.session.query(Column).filter(
                    Column.table_id == table.table_id,
                    Column.name == col_doc.column_name
                ).first()
                
                if column:
                    column.display_name = col_doc.display_name
                    column.description = col_doc.description
                    column.usage_type = col_doc.usage_type.value
                    column.metadata = {
                        **(column.metadata or {}),
                        'business_description': col_doc.business_description,
                        'example_values': col_doc.example_values,
                        'business_rules': col_doc.business_rules,
                        'data_quality_checks': col_doc.data_quality_checks,
                        'related_concepts': col_doc.related_concepts,
                        'privacy_classification': col_doc.privacy_classification,
                        'aggregation_suggestions': col_doc.aggregation_suggestions,
                        'filtering_suggestions': col_doc.filtering_suggestions,
                        'documentation_metadata': col_doc.metadata,
                        'documentation_generated_at': datetime.utcnow().isoformat()
                    }
            
            self.session.commit()
            return True
            
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Failed to update database with documentation: {str(e)}")
    
    async def _get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample data from table"""
        try:
            # This is a simplified version - in production, use proper query building
            query = text(f"SELECT * FROM {table_name} LIMIT {limit}")
            result = self.session.execute(query)
            
            sample_data = []
            for row in result:
                sample_data.append(dict(row._mapping))
            
            return sample_data
        except Exception as e:
            print(f"Warning: Could not fetch sample data for {table_name}: {str(e)}")
            return []


# ============================================================================
# API MODELS FOR SCHEMA DOCUMENTATION
# ============================================================================

class DocumentSchemaRequest(BaseModel):
    """Request model for schema documentation"""
    
    # Schema source (one of these)
    ddl_statement: Optional[str] = None
    table_name: Optional[str] = None
    schema_json: Optional[Dict[str, Any]] = None
    
    # Project context
    business_domain: str = Field(..., description="Business domain (e.g., 'training_management')")
    purpose: str = Field(..., description="Project purpose and goals")
    target_users: List[str] = Field(..., description="Target user types")
    key_business_concepts: List[str] = Field(..., description="Key business concepts")
    data_sources: Optional[List[str]] = None
    compliance_requirements: Optional[List[str]] = None
    
    # Options
    include_sample_data: bool = False
    update_database: bool = True


class DocumentedColumnResponse(BaseModel):
    """Response model for documented column"""
    
    column_name: str
    display_name: str
    description: str
    business_description: str
    usage_type: str
    data_type: str
    example_values: List[str]
    business_rules: List[str]
    data_quality_checks: List[str]
    related_concepts: List[str]
    privacy_classification: str
    aggregation_suggestions: List[str]
    filtering_suggestions: List[str]
    metadata: Dict[str, Any]


class DocumentedTableResponse(BaseModel):
    """Response model for documented table"""
    
    table_name: str
    display_name: str
    description: str
    business_purpose: str
    primary_use_cases: List[str]
    key_relationships: List[str]
    columns: List[DocumentedColumnResponse]
    data_lineage: Optional[str]
    update_frequency: str
    data_retention: Optional[str]
    access_patterns: List[str]
    performance_considerations: List[str]


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

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


async def demo_schema_documentation():
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
    # documented_table = await service.document_schema_from_json(schema_json, project_context)
    
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


if __name__ == "__main__":
    asyncio.run(demo_schema_documentation())