from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from datetime import datetime

# ============================================================================
# DATA MODELS
# ============================================================================

class ProjectContextModel(BaseModel):
    """Business context for schema documentation (Pydantic version)"""
    project_id: str
    project_name: str
    business_domain: str
    purpose: str
    target_users: List[str]
    key_business_concepts: List[str]
    data_sources: Optional[List[str]] = None
    compliance_requirements: Optional[List[str]] = None

class CreateProjectRequest(BaseModel):
    """Request model for creating projects"""
    project_id: str = Field(..., description="Project ID")
    display_name: str = Field(..., description="Display name for the project")
    description: str = Field(..., description="Description of the project")
    created_by: str = Field(..., description="User creating the project")
    context: ProjectContextModel | None = Field(..., description="Business context for the project")



class ProjectResponse(BaseModel):
    project_id: str
    display_name: str
    description: str | None = None
    created_by: str | None = None
    status: str
    version_string: str # Use the hybrid_property
    created_at: datetime
    updated_at: datetime

    # This is the magic that allows Pydantic to read from SQLAlchemy models
    class Config:
        from_attributes = True # For Pydantic v2
        # orm_mode = True # For Pydantic v1


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
    json_metadata: Dict[str, Any]


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
    semantic_description: Optional[Dict[str, Any]] = None
    relationship_recommendations: Optional[Dict[str, Any]] = None


class ColumnDocumentationSchema(BaseModel):
    """Schema for column documentation output"""
    display_name: str = Field(description="Business-friendly column name")
    description: str = Field(description="Technical description for developers")
    business_description: str = Field(description="Business description for analysts and managers")
    usage_type: str = Field(description="dimension|measure|attribute|identifier|timestamp|flag|metadata|calculated")
    example_values: List[str] = Field(description="Example values for the column")
    business_rules: List[str] = Field(description="Business rules applicable to this column")
    data_quality_checks: List[str] = Field(description="Data quality checks for this column")
    related_concepts: List[str] = Field(description="Related business concepts")
    privacy_classification: str = Field(description="public|internal|confidential|restricted")
    aggregation_suggestions: List[str] = Field(description="Suggested aggregations for this column")
    filtering_suggestions: List[str] = Field(description="Suggested filters for this column")
    json_metadata: Dict[str, Any] = Field(description="Additional metadata about the column")

    class Config:
        json_schema_extra = {
            "example": {
                "display_name": "Employee ID",
                "description": "Unique identifier for employees",
                "business_description": "Employee identification number used for HR records",
                "usage_type": "identifier",
                "example_values": ["EMP001", "EMP002"],
                "business_rules": ["Must be unique", "Cannot be null"],
                "data_quality_checks": ["Check for duplicates", "Validate format"],
                "related_concepts": ["Employee", "HR Records"],
                "privacy_classification": "internal",
                "aggregation_suggestions": ["COUNT"],
                "filtering_suggestions": ["Filter by department", "Filter by status"],
                "json_metadata": {
                    "typical_cardinality": "high",
                    "common_patterns": ["EMP###"],
                    "business_importance": "critical",
                    "analysis_frequency": "daily"
                }
            }
        }




class DefinitionType(Enum):
    """Types of definitions that can be created"""
    METRIC = "metric"
    VIEW = "view"
    CALCULATED_COLUMN = "calculated_column"
    SQL_PAIR = "sql_pair"
    INSTRUCTION = "instruction"


@dataclass
class UserExample:
    """User-provided example for creating definitions"""
    definition_type: DefinitionType
    name: str
    description: str
    sql: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None
    user_id: str = "system"


@dataclass
class GeneratedDefinition:
    """Generated definition with LLM enhancements"""
    definition_type: DefinitionType
    name: str
    display_name: str
    description: str
    sql_query: str
    chain_of_thought: str
    related_tables: List[str]
    related_columns: List[str]
    json_metadata: Dict[str, Any]
    confidence_score: float
    suggestions: List[str]


class AddTableRequest(BaseModel):
    dataset_id: str
    schema: SchemaInput



# Import your models (assuming they're in a models.py file)
# from models import Base, Project, Table, SQLColumn, Metric, View, CalculatedColumn

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================

class ProjectCreate(BaseModel):
    project_id: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=200)
    description: Optional[str] = None
    created_by: str = Field(..., max_length=100)

class ProjectUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None

class TableCreate(BaseModel):
    name: str = Field(..., max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    table_type: str = Field(default="table")
    dataset_id: Optional[str] = None

class ColumnCreate(BaseModel):
    name: str = Field(..., max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    data_type: Optional[str] = None
    is_nullable: bool = True
    is_primary_key: bool = False

class MetricCreate(BaseModel):
    name: str = Field(..., max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    metric_sql: str
    metric_type: Optional[str] = None
    aggregation_type: Optional[str] = None

class ViewCreate(BaseModel):
    name: str = Field(..., max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    view_sql: str
    view_type: Optional[str] = None

class CalculatedColumnCreate(BaseModel):
    """Request model for creating calculated columns as SQLColumns"""
    name: str = Field(..., description="Column name")
    display_name: Optional[str] = Field(None, description="Display name for the column")
    description: Optional[str] = Field(None, description="Column description")
    calculation_sql: str = Field(..., description="SQL calculation expression")
    data_type: str = Field(..., description="Data type of the calculated column")
    usage_type: Optional[str] = Field("calculated", description="Usage type (default: calculated)")
    is_nullable: bool = Field(True, description="Whether the column can be null")
    is_primary_key: bool = Field(False, description="Whether this is a primary key")
    is_foreign_key: bool = Field(False, description="Whether this is a foreign key")
    default_value: Optional[str] = Field(None, description="Default value for the column")
    ordinal_position: Optional[int] = Field(None, description="Position of the column in the table")
    function_id: Optional[str] = Field(None, description="Associated SQL function ID")
    dependencies: Optional[List[str]] = Field([], description="List of column dependencies")
    json_metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

# Response models
class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    project_id: str
    display_name: str
    description: Optional[str]
    status: str
    is_draft: bool
    version_string: str
    created_at: datetime
    table_count: int = 0

class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    table_id: str
    name: str
    display_name: Optional[str]
    description: Optional[str]
    table_type: str
    semantic_description: Optional[str] = None
    column_count: int = 0


# ============================================================================
# EXAMPLE API MODELS
# ============================================================================

class ExampleCreate(BaseModel):
    """Request model for creating examples"""
    project_id: str = Field(..., description="Project ID")
    definition_type: DefinitionType = Field(..., description="Type of definition")
    name: str = Field(..., description="Example name")
    question: str = Field(..., description="Question or description")
    sql_query: str = Field(..., description="SQL query")
    context: Optional[str] = Field(None, description="Additional context")
    document_reference: Optional[str] = Field(None, description="Document reference")
    instructions: Optional[str] = Field(None, description="Instructions")
    categories: Optional[List[str]] = Field(default=[], description="Categories")
    samples: Optional[List[Dict[str, Any]]] = Field(default=[], description="Sample data")
    additional_context: Optional[Dict[str, Any]] = Field(default={}, description="Additional context")
    user_id: str = Field(default="system", description="User ID")
    json_metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class ExampleUpdate(BaseModel):
    """Request model for updating examples"""
    definition_type: Optional[DefinitionType] = Field(None, description="Type of definition")
    name: Optional[str] = Field(None, description="Example name")
    question: Optional[str] = Field(None, description="Question or description")
    sql_query: Optional[str] = Field(None, description="SQL query")
    context: Optional[str] = Field(None, description="Additional context")
    document_reference: Optional[str] = Field(None, description="Document reference")
    instructions: Optional[str] = Field(None, description="Instructions")
    categories: Optional[List[str]] = Field(None, description="Categories")
    samples: Optional[List[Dict[str, Any]]] = Field(None, description="Sample data")
    additional_context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    user_id: Optional[str] = Field(None, description="User ID")
    json_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ExampleRead(BaseModel):
    """Response model for examples"""
    model_config = ConfigDict(from_attributes=True)
    
    example_id: str
    project_id: str
    definition_type: str
    name: str
    question: str
    sql_query: str
    context: Optional[str]
    document_reference: Optional[str]
    instructions: Optional[str]
    categories: Optional[List[str]]
    samples: Optional[List[Dict[str, Any]]]
    additional_context: Optional[Dict[str, Any]]
    user_id: str
    json_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    entity_version: int
    modified_by: Optional[str]


# ============================================================================
# USER EXAMPLE API MODELS
# ============================================================================

class UserExampleCreate(BaseModel):
    """Request model for creating user examples"""
    project_id: str = Field(..., description="Project ID")
    definition_type: DefinitionType = Field(..., description="Type of definition")
    name: str = Field(..., description="Example name")
    description: str = Field(..., description="Example description")
    sql: Optional[str] = Field(None, description="SQL query")
    additional_context: Optional[Dict[str, Any]] = Field(default={}, description="Additional context")
    user_id: str = Field(default="system", description="User ID")


class UserExampleUpdate(BaseModel):
    """Request model for updating user examples"""
    definition_type: Optional[DefinitionType] = Field(None, description="Type of definition")
    name: Optional[str] = Field(None, description="Example name")
    description: Optional[str] = Field(None, description="Example description")
    sql: Optional[str] = Field(None, description="SQL query")
    additional_context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class UserExampleRead(BaseModel):
    """Response model for user examples"""
    model_config = ConfigDict(from_attributes=True)
    
    example_id: str
    project_id: str
    definition_type: str
    name: str
    question: str
    sql_query: str
    context: Optional[str]
    document_reference: Optional[str]
    instructions: Optional[str]
    categories: Optional[List[str]]
    samples: Optional[List[Dict[str, Any]]]
    additional_context: Optional[Dict[str, Any]]
    user_id: str
    json_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    entity_version: int
    modified_by: Optional[str]


# ============================================================================
# INSTRUCTION API MODELS
# ============================================================================

class InstructionCreate(BaseModel):
    """Request model for creating instructions"""
    project_id: str = Field(..., description="Project ID")
    question: str = Field(..., description="Question or instruction title")
    instructions: str = Field(..., description="Detailed instructions")
    sql_query: str = Field(..., description="SQL query")
    chain_of_thought: Optional[str] = Field(None, description="Chain of thought reasoning")
    json_metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class InstructionUpdate(BaseModel):
    """Request model for updating instructions"""
    question: Optional[str] = Field(None, description="Question or instruction title")
    instructions: Optional[str] = Field(None, description="Detailed instructions")
    sql_query: Optional[str] = Field(None, description="SQL query")
    chain_of_thought: Optional[str] = Field(None, description="Chain of thought reasoning")
    json_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class InstructionRead(BaseModel):
    """Response model for instructions"""
    model_config = ConfigDict(from_attributes=True)
    
    instruction_id: str
    project_id: str
    question: str
    instructions: str
    sql_query: str
    chain_of_thought: Optional[str]
    json_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    entity_version: int
    modified_by: Optional[str]


# ============================================================================
# KNOWLEDGE BASE API MODELS
# ============================================================================

class KnowledgeBaseCreate(BaseModel):
    """Request model for creating knowledge base entries"""
    project_id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Knowledge base entry name")
    display_name: Optional[str] = Field(None, description="Display name")
    description: Optional[str] = Field(None, description="Description")
    file_path: Optional[str] = Field(None, description="File path")
    content_type: str = Field(default="text", description="Content type (text, markdown, json, etc.)")
    content: Optional[str] = Field(None, description="Content")
    json_metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class KnowledgeBaseUpdate(BaseModel):
    """Request model for updating knowledge base entries"""
    name: Optional[str] = Field(None, description="Knowledge base entry name")
    display_name: Optional[str] = Field(None, description="Display name")
    description: Optional[str] = Field(None, description="Description")
    file_path: Optional[str] = Field(None, description="File path")
    content_type: Optional[str] = Field(None, description="Content type")
    content: Optional[str] = Field(None, description="Content")
    json_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class KnowledgeBaseRead(BaseModel):
    """Response model for knowledge base entries"""
    model_config = ConfigDict(from_attributes=True)
    
    kb_id: str
    project_id: str
    name: str
    display_name: Optional[str]
    description: Optional[str]
    file_path: Optional[str]
    content_type: str
    content: Optional[str]
    json_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    entity_version: int
    modified_by: Optional[str]