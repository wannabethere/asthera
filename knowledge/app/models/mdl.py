"""
MDL Edge Type Definitions and Utilities

Defines all MDL (Metadata Definition Language) edge types with:
- Semantic meaning
- Priority scores
- Valid source/target entity types
- Metadata requirements

These edge types support the MDL semantic layer for database schema,
tables, columns, relationships, features, metrics, and examples.
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class MDLEntityType(str, Enum):
    """Valid MDL entity types for edge endpoints"""
    PRODUCT = "product"
    CATEGORY = "category"
    SCHEMA = "schema"
    TABLE = "table"
    COLUMN = "column"
    RELATIONSHIP = "relationship"
    FEATURE = "feature"
    CONTROL = "control"
    METRIC = "metric"
    KPI = "kpi"
    EXAMPLE = "example"
    NATURAL_QUESTION = "natural_question"
    INSTRUCTION = "instruction"
    QUERY_PATTERN = "query_pattern"


class MDLEdgeType(str, Enum):
    """MDL edge types for contextual graph"""
    # Schema/Table/Column hierarchy
    BELONGS_TO_TABLE = "BELONGS_TO_TABLE"  # Column belongs to table
    HAS_MANY_TABLES = "HAS_MANY_TABLES"  # Schema has many tables
    HAS_COLUMN = "HAS_COLUMN"  # Table has column (inverse of BELONGS_TO_TABLE)
    
    # Table relationships
    RELATES_TO_TABLE = "RELATES_TO_TABLE"  # Table-to-table relationship (join)
    DERIVED_FROM = "DERIVED_FROM"  # Derived/calculated columns
    
    # Category groupings
    CATEGORY_CONTAINS_TABLE = "CATEGORY_CONTAINS_TABLE"  # Category groups tables
    PRODUCT_HAS_CATEGORY = "PRODUCT_HAS_CATEGORY"  # Product has category
    TABLE_IN_CATEGORY = "TABLE_IN_CATEGORY"  # Table belongs to category
    
    # Feature relationships
    TABLE_HAS_FEATURE = "TABLE_HAS_FEATURE"  # Feature is derived from table
    COLUMN_SUPPORTS_FEATURE = "COLUMN_SUPPORTS_FEATURE"  # Column used in feature
    FEATURE_DEPENDS_ON_FEATURE = "FEATURE_DEPENDS_ON_FEATURE"  # Feature dependencies
    
    # Compliance/Control relationships
    FEATURE_SUPPORTS_CONTROL = "FEATURE_SUPPORTS_CONTROL"  # Feature supports control
    TABLE_PROVIDES_EVIDENCE = "TABLE_PROVIDES_EVIDENCE"  # Table provides control evidence
    COLUMN_PROVIDES_EVIDENCE = "COLUMN_PROVIDES_EVIDENCE"  # Column provides control evidence
    
    # Metrics and KPIs
    METRIC_FROM_TABLE = "METRIC_FROM_TABLE"  # Metric calculated from table
    METRIC_FROM_COLUMN = "METRIC_FROM_COLUMN"  # Metric calculated from column
    KPI_FROM_METRIC = "KPI_FROM_METRIC"  # KPI based on metric
    
    # Examples and usage patterns
    EXAMPLE_USES_TABLE = "EXAMPLE_USES_TABLE"  # Example query uses table
    EXAMPLE_USES_COLUMN = "EXAMPLE_USES_COLUMN"  # Example query uses column
    QUESTION_ANSWERED_BY_TABLE = "QUESTION_ANSWERED_BY_TABLE"  # Question can be answered by table
    QUESTION_ANSWERED_BY_COLUMN = "QUESTION_ANSWERED_BY_COLUMN"  # Question can be answered by column
    
    # Product-specific instructions
    INSTRUCTION_APPLIES_TO_PRODUCT = "INSTRUCTION_APPLIES_TO_PRODUCT"  # Instruction for product
    INSTRUCTION_APPLIES_TO_TABLE = "INSTRUCTION_APPLIES_TO_TABLE"  # Instruction for specific table
    INSTRUCTION_APPLIES_TO_CATEGORY = "INSTRUCTION_APPLIES_TO_CATEGORY"  # Instruction for category
    
    # Query patterns
    PATTERN_USES_TABLE = "PATTERN_USES_TABLE"  # Query pattern uses table
    PATTERN_USES_RELATIONSHIP = "PATTERN_USES_RELATIONSHIP"  # Query pattern uses relationship


@dataclass
class MDLEdgeTypeDefinition:
    """Complete definition of an MDL edge type"""
    edge_type: MDLEdgeType
    description: str
    semantic_meaning: str
    priority: float  # 0.0-1.0, higher is more important
    valid_source_types: List[MDLEntityType]
    valid_target_types: List[MDLEntityType]
    required_metadata: List[str] = field(default_factory=list)
    optional_metadata: List[str] = field(default_factory=list)
    bidirectional: bool = False
    examples: List[str] = field(default_factory=list)
    
    def is_valid_edge(
        self,
        source_type: str,
        target_type: str
    ) -> bool:
        """Check if source and target types are valid for this edge type"""
        try:
            source_enum = MDLEntityType(source_type)
            target_enum = MDLEntityType(target_type)
            return (
                source_enum in self.valid_source_types and
                target_enum in self.valid_target_types
            )
        except (ValueError, KeyError):
            return False


# Define all MDL edge types
MDL_EDGE_TYPE_DEFINITIONS: Dict[MDLEdgeType, MDLEdgeTypeDefinition] = {
    MDLEdgeType.BELONGS_TO_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.BELONGS_TO_TABLE,
        description="Column belongs to a table",
        semantic_meaning="Represents the fundamental relationship between a column and its parent table in the database schema",
        priority=0.95,
        valid_source_types=[MDLEntityType.COLUMN],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["column_name", "table_name", "data_type"],
        optional_metadata=["is_primary_key", "is_foreign_key", "is_nullable", "default_value"],
        examples=["Column 'id' belongs to table 'AssetAttributes'", "Column 'email' belongs to table 'Users'"]
    ),
    
    MDLEdgeType.HAS_MANY_TABLES: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.HAS_MANY_TABLES,
        description="Schema contains multiple tables",
        semantic_meaning="Represents the organizational relationship between a schema/database and its tables",
        priority=0.8,
        valid_source_types=[MDLEntityType.SCHEMA, MDLEntityType.PRODUCT],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["schema_name", "table_name"],
        optional_metadata=["table_count"],
        examples=["Snyk schema contains 'AssetAttributes' table", "Database has 'Projects' table"]
    ),
    
    MDLEdgeType.HAS_COLUMN: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.HAS_COLUMN,
        description="Table has a column",
        semantic_meaning="Inverse relationship of BELONGS_TO_TABLE, useful for table-centric queries",
        priority=0.9,
        valid_source_types=[MDLEntityType.TABLE],
        valid_target_types=[MDLEntityType.COLUMN],
        required_metadata=["table_name", "column_name"],
        optional_metadata=["column_order", "is_indexed"],
        examples=["Table 'AssetAttributes' has column 'id'", "Table 'Users' has column 'email'"]
    ),
    
    MDLEdgeType.RELATES_TO_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.RELATES_TO_TABLE,
        description="Table-to-table relationship (foreign key, join)",
        semantic_meaning="Represents relationships between tables through foreign keys or logical joins",
        priority=0.85,
        valid_source_types=[MDLEntityType.TABLE],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["source_table", "target_table", "relationship_type"],
        optional_metadata=["join_column", "cardinality", "relationship_name"],
        bidirectional=True,
        examples=[
            "Table 'AssetAttributes' relates to 'AssetClass' via asset_class_id",
            "Projects table relates to Organizations table"
        ]
    ),
    
    MDLEdgeType.DERIVED_FROM: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.DERIVED_FROM,
        description="Derived or calculated column",
        semantic_meaning="Column is calculated or derived from other columns or tables",
        priority=0.75,
        valid_source_types=[MDLEntityType.COLUMN],
        valid_target_types=[MDLEntityType.COLUMN, MDLEntityType.TABLE],
        required_metadata=["derived_column", "source_entity", "calculation_logic"],
        optional_metadata=["dependencies"],
        examples=[
            "Column 'full_name' derived from 'first_name' and 'last_name'",
            "Column 'risk_score' calculated from vulnerability data"
        ]
    ),
    
    MDLEdgeType.CATEGORY_CONTAINS_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.CATEGORY_CONTAINS_TABLE,
        description="Category groups related tables",
        semantic_meaning="Logical grouping of tables by business domain or functionality",
        priority=0.8,
        valid_source_types=[MDLEntityType.CATEGORY],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["category_name", "table_name"],
        optional_metadata=["category_description", "table_count"],
        examples=[
            "Category 'assets' contains table 'AssetAttributes'",
            "Category 'vulnerabilities' contains table 'VulnerabilityInstances'"
        ]
    ),
    
    MDLEdgeType.PRODUCT_HAS_CATEGORY: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.PRODUCT_HAS_CATEGORY,
        description="Product organizes data into categories",
        semantic_meaning="Top-level organization of a product's data model by category",
        priority=0.7,
        valid_source_types=[MDLEntityType.PRODUCT],
        valid_target_types=[MDLEntityType.CATEGORY],
        required_metadata=["product_name", "category_name"],
        optional_metadata=["category_priority"],
        examples=["Snyk has category 'assets'", "Cornerstone has category 'compliance'"]
    ),
    
    MDLEdgeType.TABLE_IN_CATEGORY: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.TABLE_IN_CATEGORY,
        description="Table belongs to a category",
        semantic_meaning="Inverse of CATEGORY_CONTAINS_TABLE, table-centric view",
        priority=0.8,
        valid_source_types=[MDLEntityType.TABLE],
        valid_target_types=[MDLEntityType.CATEGORY],
        required_metadata=["table_name", "category_name"],
        optional_metadata=["category_fit_score"],
        examples=["Table 'AssetAttributes' is in category 'assets'"]
    ),
    
    MDLEdgeType.TABLE_HAS_FEATURE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.TABLE_HAS_FEATURE,
        description="Feature is derived from table",
        semantic_meaning="Business feature or capability provided by a table",
        priority=0.85,
        valid_source_types=[MDLEntityType.TABLE],
        valid_target_types=[MDLEntityType.FEATURE],
        required_metadata=["table_name", "feature_name"],
        optional_metadata=["feature_description", "implementation_details"],
        examples=[
            "Table 'AssetAttributes' provides feature 'asset tracking'",
            "Table 'VulnerabilityInstances' provides feature 'vulnerability monitoring'"
        ]
    ),
    
    MDLEdgeType.COLUMN_SUPPORTS_FEATURE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.COLUMN_SUPPORTS_FEATURE,
        description="Column is used in a feature",
        semantic_meaning="Specific column contributes to a business feature",
        priority=0.75,
        valid_source_types=[MDLEntityType.COLUMN],
        valid_target_types=[MDLEntityType.FEATURE],
        required_metadata=["column_name", "feature_name"],
        optional_metadata=["usage_type"],
        examples=["Column 'severity' supports feature 'risk scoring'"]
    ),
    
    MDLEdgeType.FEATURE_DEPENDS_ON_FEATURE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.FEATURE_DEPENDS_ON_FEATURE,
        description="Feature depends on another feature",
        semantic_meaning="Feature dependencies and composition relationships",
        priority=0.7,
        valid_source_types=[MDLEntityType.FEATURE],
        valid_target_types=[MDLEntityType.FEATURE],
        required_metadata=["dependent_feature", "required_feature"],
        optional_metadata=["dependency_type"],
        examples=["Feature 'risk_score' depends on feature 'vulnerability_count'"]
    ),
    
    MDLEdgeType.FEATURE_SUPPORTS_CONTROL: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.FEATURE_SUPPORTS_CONTROL,
        description="Feature supports a compliance control",
        semantic_meaning="Links business features to compliance controls they help satisfy",
        priority=0.9,
        valid_source_types=[MDLEntityType.FEATURE],
        valid_target_types=[MDLEntityType.CONTROL],
        required_metadata=["feature_name", "control_id"],
        optional_metadata=["framework", "evidence_type"],
        examples=[
            "Feature 'access_monitoring' supports control 'CC6.1'",
            "Feature 'encryption_tracking' supports HIPAA control"
        ]
    ),
    
    MDLEdgeType.TABLE_PROVIDES_EVIDENCE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.TABLE_PROVIDES_EVIDENCE,
        description="Table provides evidence for a control",
        semantic_meaning="Direct relationship between data tables and compliance evidence",
        priority=0.85,
        valid_source_types=[MDLEntityType.TABLE],
        valid_target_types=[MDLEntityType.CONTROL],
        required_metadata=["table_name", "control_id"],
        optional_metadata=["evidence_description", "framework"],
        examples=["Table 'AuditLogs' provides evidence for logging controls"]
    ),
    
    MDLEdgeType.COLUMN_PROVIDES_EVIDENCE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.COLUMN_PROVIDES_EVIDENCE,
        description="Specific column provides control evidence",
        semantic_meaning="Granular mapping of columns to compliance evidence requirements",
        priority=0.8,
        valid_source_types=[MDLEntityType.COLUMN],
        valid_target_types=[MDLEntityType.CONTROL],
        required_metadata=["column_name", "control_id"],
        optional_metadata=["evidence_type"],
        examples=["Column 'encryption_status' provides evidence for encryption controls"]
    ),
    
    MDLEdgeType.METRIC_FROM_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.METRIC_FROM_TABLE,
        description="Metric calculated from table",
        semantic_meaning="Business metric derived from table data",
        priority=0.8,
        valid_source_types=[MDLEntityType.METRIC, MDLEntityType.KPI],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["metric_name", "table_name"],
        optional_metadata=["calculation_method", "aggregation_type"],
        examples=["Metric 'total_assets' calculated from 'AssetAttributes' table"]
    ),
    
    MDLEdgeType.METRIC_FROM_COLUMN: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.METRIC_FROM_COLUMN,
        description="Metric calculated from specific column",
        semantic_meaning="Granular metric based on specific column data",
        priority=0.75,
        valid_source_types=[MDLEntityType.METRIC, MDLEntityType.KPI],
        valid_target_types=[MDLEntityType.COLUMN],
        required_metadata=["metric_name", "column_name"],
        optional_metadata=["aggregation_function"],
        examples=["Metric 'avg_risk_score' calculated from 'risk_score' column"]
    ),
    
    MDLEdgeType.KPI_FROM_METRIC: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.KPI_FROM_METRIC,
        description="KPI based on metric",
        semantic_meaning="High-level KPI composed from metrics",
        priority=0.7,
        valid_source_types=[MDLEntityType.KPI],
        valid_target_types=[MDLEntityType.METRIC],
        required_metadata=["kpi_name", "metric_name"],
        optional_metadata=["threshold", "target_value"],
        examples=["KPI 'security_posture' based on multiple risk metrics"]
    ),
    
    MDLEdgeType.EXAMPLE_USES_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.EXAMPLE_USES_TABLE,
        description="Example query uses table",
        semantic_meaning="Links example queries to the tables they reference",
        priority=0.85,
        valid_source_types=[MDLEntityType.EXAMPLE, MDLEntityType.QUERY_PATTERN],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["example_id", "table_name"],
        optional_metadata=["query_text", "use_case"],
        examples=["Example 'get_asset_count' uses table 'AssetAttributes'"]
    ),
    
    MDLEdgeType.EXAMPLE_USES_COLUMN: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.EXAMPLE_USES_COLUMN,
        description="Example query uses column",
        semantic_meaning="Links example queries to specific columns they reference",
        priority=0.8,
        valid_source_types=[MDLEntityType.EXAMPLE, MDLEntityType.QUERY_PATTERN],
        valid_target_types=[MDLEntityType.COLUMN],
        required_metadata=["example_id", "column_name"],
        optional_metadata=["usage_purpose"],
        examples=["Example filters by column 'severity'"]
    ),
    
    MDLEdgeType.QUESTION_ANSWERED_BY_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.QUESTION_ANSWERED_BY_TABLE,
        description="Natural language question can be answered by table",
        semantic_meaning="Maps user questions to relevant tables",
        priority=0.9,
        valid_source_types=[MDLEntityType.NATURAL_QUESTION],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["question", "table_name"],
        optional_metadata=["confidence_score"],
        examples=["Question 'How many assets do we have?' answered by 'AssetAttributes'"]
    ),
    
    MDLEdgeType.QUESTION_ANSWERED_BY_COLUMN: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.QUESTION_ANSWERED_BY_COLUMN,
        description="Natural language question references specific column",
        semantic_meaning="Maps user questions to relevant columns",
        priority=0.85,
        valid_source_types=[MDLEntityType.NATURAL_QUESTION],
        valid_target_types=[MDLEntityType.COLUMN],
        required_metadata=["question", "column_name"],
        optional_metadata=["relevance_score"],
        examples=["Question about severity answered by 'severity' column"]
    ),
    
    MDLEdgeType.INSTRUCTION_APPLIES_TO_PRODUCT: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.INSTRUCTION_APPLIES_TO_PRODUCT,
        description="Product-specific instruction or best practice",
        semantic_meaning="General instructions for working with a product",
        priority=0.75,
        valid_source_types=[MDLEntityType.INSTRUCTION],
        valid_target_types=[MDLEntityType.PRODUCT],
        required_metadata=["instruction_id", "product_name"],
        optional_metadata=["instruction_type"],
        examples=["Instruction 'use API v3' applies to Snyk product"]
    ),
    
    MDLEdgeType.INSTRUCTION_APPLIES_TO_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.INSTRUCTION_APPLIES_TO_TABLE,
        description="Table-specific instruction",
        semantic_meaning="Specific guidance for working with a table",
        priority=0.8,
        valid_source_types=[MDLEntityType.INSTRUCTION],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["instruction_id", "table_name"],
        optional_metadata=["usage_context"],
        examples=["Instruction 'join with AssetClass' applies to 'AssetAttributes'"]
    ),
    
    MDLEdgeType.INSTRUCTION_APPLIES_TO_CATEGORY: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.INSTRUCTION_APPLIES_TO_CATEGORY,
        description="Category-specific instruction",
        semantic_meaning="Guidance for working with a category of tables",
        priority=0.75,
        valid_source_types=[MDLEntityType.INSTRUCTION],
        valid_target_types=[MDLEntityType.CATEGORY],
        required_metadata=["instruction_id", "category_name"],
        optional_metadata=["best_practices"],
        examples=["Instruction 'always filter by active' applies to 'assets' category"]
    ),
    
    MDLEdgeType.PATTERN_USES_TABLE: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.PATTERN_USES_TABLE,
        description="Query pattern uses table",
        semantic_meaning="Common query patterns involving specific tables",
        priority=0.8,
        valid_source_types=[MDLEntityType.QUERY_PATTERN],
        valid_target_types=[MDLEntityType.TABLE],
        required_metadata=["pattern_id", "table_name"],
        optional_metadata=["pattern_type", "frequency"],
        examples=["Pattern 'asset_summary' uses 'AssetAttributes' and 'AssetClass'"]
    ),
    
    MDLEdgeType.PATTERN_USES_RELATIONSHIP: MDLEdgeTypeDefinition(
        edge_type=MDLEdgeType.PATTERN_USES_RELATIONSHIP,
        description="Query pattern uses table relationship",
        semantic_meaning="Query patterns that leverage table joins",
        priority=0.75,
        valid_source_types=[MDLEntityType.QUERY_PATTERN],
        valid_target_types=[MDLEntityType.RELATIONSHIP],
        required_metadata=["pattern_id", "relationship_name"],
        optional_metadata=["join_type"],
        examples=["Pattern uses 'AssetAttributes -> AssetClass' relationship"]
    ),
}


def get_mdl_edge_type_semantics() -> Dict[str, Dict[str, Any]]:
    """
    Get semantics for all MDL edge types.
    
    Returns:
        Dictionary mapping edge type names to their semantic information
    """
    return {
        edge_type.value: {
            "description": definition.description,
            "semantic_meaning": definition.semantic_meaning,
            "priority": definition.priority,
            "valid_source_types": [t.value for t in definition.valid_source_types],
            "valid_target_types": [t.value for t in definition.valid_target_types],
            "required_metadata": definition.required_metadata,
            "optional_metadata": definition.optional_metadata,
            "bidirectional": definition.bidirectional,
            "examples": definition.examples
        }
        for edge_type, definition in MDL_EDGE_TYPE_DEFINITIONS.items()
    }


def get_edge_type_priority(edge_type: str) -> float:
    """
    Get priority score for an MDL edge type.
    
    Args:
        edge_type: Edge type string (e.g., "BELONGS_TO_TABLE")
        
    Returns:
        Priority score (0.0-1.0), or 0.5 if edge type not found
    """
    try:
        edge_enum = MDLEdgeType(edge_type)
        definition = MDL_EDGE_TYPE_DEFINITIONS.get(edge_enum)
        return definition.priority if definition else 0.5
    except (ValueError, KeyError):
        return 0.5


def validate_mdl_edge(
    edge_type: str,
    source_entity_type: str,
    target_entity_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str]]:
    """
    Validate an MDL edge structure.
    
    Args:
        edge_type: Edge type string
        source_entity_type: Source entity type
        target_entity_type: Target entity type
        metadata: Optional edge metadata
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check if edge type is valid
    try:
        edge_enum = MDLEdgeType(edge_type)
    except ValueError:
        errors.append(f"Invalid edge type: {edge_type}")
        return False, errors
    
    # Get edge definition
    definition = MDL_EDGE_TYPE_DEFINITIONS.get(edge_enum)
    if not definition:
        errors.append(f"No definition found for edge type: {edge_type}")
        return False, errors
    
    # Validate source and target types
    if not definition.is_valid_edge(source_entity_type, target_entity_type):
        errors.append(
            f"Invalid entity types for {edge_type}: "
            f"source={source_entity_type}, target={target_entity_type}. "
            f"Valid sources: {[t.value for t in definition.valid_source_types]}, "
            f"Valid targets: {[t.value for t in definition.valid_target_types]}"
        )
    
    # Validate required metadata
    if metadata:
        for required_field in definition.required_metadata:
            if required_field not in metadata:
                errors.append(f"Missing required metadata field: {required_field}")
    else:
        if definition.required_metadata:
            errors.append(f"Missing required metadata fields: {definition.required_metadata}")
    
    return len(errors) == 0, errors


def get_edge_types_by_priority() -> List[Tuple[MDLEdgeType, float]]:
    """
    Get all edge types sorted by priority (descending).
    
    Returns:
        List of (edge_type, priority) tuples sorted by priority
    """
    edge_priorities = [
        (edge_type, definition.priority)
        for edge_type, definition in MDL_EDGE_TYPE_DEFINITIONS.items()
    ]
    return sorted(edge_priorities, key=lambda x: x[1], reverse=True)


def get_edge_types_for_entity(
    entity_type: str,
    as_source: bool = True
) -> List[MDLEdgeType]:
    """
    Get valid edge types for an entity type.
    
    Args:
        entity_type: Entity type string
        as_source: If True, get edge types where entity is source; 
                  if False, get where entity is target
        
    Returns:
        List of valid edge types
    """
    try:
        entity_enum = MDLEntityType(entity_type)
    except ValueError:
        return []
    
    valid_edges = []
    for edge_type, definition in MDL_EDGE_TYPE_DEFINITIONS.items():
        if as_source:
            if entity_enum in definition.valid_source_types:
                valid_edges.append(edge_type)
        else:
            if entity_enum in definition.valid_target_types:
                valid_edges.append(edge_type)
    
    return valid_edges


def get_mdl_categories() -> List[str]:
    """
    Get the list of MDL categories from FINAL_CATEGORIES.
    
    Returns:
        List of category names
    """
    return [
        "access requests",
        "application data",
        "assets",
        "projects",
        "vulnerabilities",
        "integrations",
        "configuration",
        "audit logs",
        "risk management",
        "deployment",
        "groups",
        "organizations",
        "memberships and roles",
        "issues",
        "artifacts"
    ]
