
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

# ============================================================================
# DATA MODELS
# ============================================================================
class CreateProjectRequest(BaseModel):
    """Request model for creating projects"""
    
    project_id: str = Field(..., description="Project ID")
    display_name: str = Field(..., description="Display name for the project")
    description: str = Field(..., description="Description of the project")
    created_by: str = Field(..., description="User creating the project")



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
    metadata: Dict[str, Any] = Field(description="Additional metadata about the column")

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
                "metadata": {
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
    metadata: Dict[str, Any]
    confidence_score: float
    suggestions: List[str]
