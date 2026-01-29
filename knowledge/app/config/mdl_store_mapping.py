"""
MDL Store Mapping Configuration

Maps MDL entity types to their corresponding ChromaDB collections and PostgreSQL tables
for hybrid search integration.

This configuration is used by:
- HybridSearchService - To query the correct collections
- MDL Context Breakdown Agent - To identify relevant stores
- MDL Edge Pruning Agent - To discover and filter edges
- Indexing CLI - To populate correct stores
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class EntityType(str, Enum):
    """MDL entity types"""
    PRODUCT = "product"
    CATEGORY = "category"
    TABLE = "table"
    COLUMN = "column"
    RELATIONSHIP = "relationship"
    INSIGHT = "insight"
    METRIC = "metric"
    FEATURE = "feature"
    EXAMPLE = "example"
    INSTRUCTION = "instruction"
    TIME_CONCEPT = "time_concept"
    CALCULATED_COLUMN = "calculated_column"
    BUSINESS_FUNCTION = "business_function"
    FRAMEWORK = "framework"
    OWNERSHIP = "ownership"
    EDGE = "edge"


class EdgeType(str, Enum):
    """MDL edge types with priorities"""
    # Critical Priority
    COLUMN_BELONGS_TO_TABLE = "COLUMN_BELONGS_TO_TABLE"
    TABLE_BELONGS_TO_CATEGORY = "TABLE_BELONGS_TO_CATEGORY"
    TABLE_RELATES_TO_TABLE = "TABLE_RELATES_TO_TABLE"
    
    # High Priority
    TABLE_HAS_FEATURE = "TABLE_HAS_FEATURE"
    FEATURE_SUPPORTS_CONTROL = "FEATURE_SUPPORTS_CONTROL"
    METRIC_FROM_TABLE = "METRIC_FROM_TABLE"
    EXAMPLE_USES_TABLE = "EXAMPLE_USES_TABLE"
    CATEGORY_BELONGS_TO_PRODUCT = "CATEGORY_BELONGS_TO_PRODUCT"
    
    # Medium Priority
    TABLE_FOLLOWS_INSTRUCTION = "TABLE_FOLLOWS_INSTRUCTION"
    INSIGHT_USES_TABLE = "INSIGHT_USES_TABLE"
    BUSINESS_FUNCTION_USES_TABLE = "BUSINESS_FUNCTION_USES_TABLE"
    TABLE_HAS_COLUMN = "TABLE_HAS_COLUMN"
    COLUMN_REFERENCES_COLUMN = "COLUMN_REFERENCES_COLUMN"
    
    # Low Priority
    OWNERSHIP_FOR_TABLE = "OWNERSHIP_FOR_TABLE"
    FRAMEWORK_MAPS_TO_TABLE = "FRAMEWORK_MAPS_TO_TABLE"
    PRODUCT_HAS_CATEGORY = "PRODUCT_HAS_CATEGORY"
    
    # Additional Edge Types
    COLUMN_IS_TIME_DIMENSION = "COLUMN_IS_TIME_DIMENSION"
    COLUMN_SUPPORTS_KPI = "COLUMN_SUPPORTS_KPI"
    COLUMN_DERIVED_FROM = "COLUMN_DERIVED_FROM"
    CALCULATED_COLUMN_BELONGS_TO_TABLE = "CALCULATED_COLUMN_BELONGS_TO_TABLE"
    CALCULATED_COLUMN_DERIVED_FROM = "CALCULATED_COLUMN_DERIVED_FROM"
    METRIC_USES_COLUMN = "METRIC_USES_COLUMN"
    FEATURE_USES_TABLE = "FEATURE_USES_TABLE"
    FEATURE_USES_COLUMN = "FEATURE_USES_COLUMN"


@dataclass
class StoreMapping:
    """Mapping of an entity type to its storage locations"""
    entity_type: EntityType
    chroma_collection: str
    postgres_table: str
    description: str
    primary_key: str
    supports_hybrid_search: bool = True
    supports_edge_discovery: bool = True


# ============================================================================
# STORE MAPPINGS
# ============================================================================

MDL_STORE_MAPPINGS: Dict[EntityType, StoreMapping] = {
    EntityType.PRODUCT: StoreMapping(
        entity_type=EntityType.PRODUCT,
        chroma_collection="mdl_products",
        postgres_table="mdl_products",
        description="Product definitions and capabilities",
        primary_key="product_id"
    ),
    
    EntityType.CATEGORY: StoreMapping(
        entity_type=EntityType.CATEGORY,
        chroma_collection="mdl_categories",
        postgres_table="mdl_categories",
        description="15 business categories",
        primary_key="category_id"
    ),
    
    EntityType.TABLE: StoreMapping(
        entity_type=EntityType.TABLE,
        chroma_collection="mdl_tables",
        postgres_table="mdl_tables",
        description="Table schemas and descriptions",
        primary_key="table_id"
    ),
    
    EntityType.COLUMN: StoreMapping(
        entity_type=EntityType.COLUMN,
        chroma_collection="mdl_columns",
        postgres_table="mdl_columns",
        description="Column metadata and semantics",
        primary_key="column_id"
    ),
    
    EntityType.RELATIONSHIP: StoreMapping(
        entity_type=EntityType.RELATIONSHIP,
        chroma_collection="mdl_relationships",
        postgres_table="mdl_relationships",
        description="Table relationships",
        primary_key="relationship_id"
    ),
    
    EntityType.INSIGHT: StoreMapping(
        entity_type=EntityType.INSIGHT,
        chroma_collection="mdl_insights",
        postgres_table="mdl_insights",
        description="Metrics, features, concepts",
        primary_key="insight_id"
    ),
    
    EntityType.METRIC: StoreMapping(
        entity_type=EntityType.METRIC,
        chroma_collection="mdl_metrics",
        postgres_table="mdl_metrics",
        description="Business metrics and KPIs",
        primary_key="metric_id"
    ),
    
    EntityType.FEATURE: StoreMapping(
        entity_type=EntityType.FEATURE,
        chroma_collection="mdl_features",
        postgres_table="mdl_features",
        description="Product features",
        primary_key="feature_id"
    ),
    
    EntityType.EXAMPLE: StoreMapping(
        entity_type=EntityType.EXAMPLE,
        chroma_collection="mdl_examples",
        postgres_table="mdl_examples",
        description="Query examples",
        primary_key="example_id"
    ),
    
    EntityType.INSTRUCTION: StoreMapping(
        entity_type=EntityType.INSTRUCTION,
        chroma_collection="mdl_instructions",
        postgres_table="mdl_instructions",
        description="Product instructions",
        primary_key="instruction_id"
    ),
    
    EntityType.TIME_CONCEPT: StoreMapping(
        entity_type=EntityType.TIME_CONCEPT,
        chroma_collection="mdl_time_concepts",
        postgres_table="mdl_time_concepts",
        description="Temporal dimensions",
        primary_key="time_concept_id"
    ),
    
    EntityType.CALCULATED_COLUMN: StoreMapping(
        entity_type=EntityType.CALCULATED_COLUMN,
        chroma_collection="mdl_calculated_columns",
        postgres_table="mdl_calculated_columns",
        description="Derived columns",
        primary_key="calculated_column_id"
    ),
    
    EntityType.BUSINESS_FUNCTION: StoreMapping(
        entity_type=EntityType.BUSINESS_FUNCTION,
        chroma_collection="mdl_business_functions",
        postgres_table="mdl_business_functions",
        description="Business capabilities",
        primary_key="business_function_id"
    ),
    
    EntityType.FRAMEWORK: StoreMapping(
        entity_type=EntityType.FRAMEWORK,
        chroma_collection="mdl_frameworks",
        postgres_table="mdl_frameworks",
        description="Compliance frameworks",
        primary_key="framework_id"
    ),
    
    EntityType.OWNERSHIP: StoreMapping(
        entity_type=EntityType.OWNERSHIP,
        chroma_collection="mdl_ownership",
        postgres_table="mdl_ownership",
        description="Access and ownership",
        primary_key="ownership_id"
    ),
    
    EntityType.EDGE: StoreMapping(
        entity_type=EntityType.EDGE,
        chroma_collection="mdl_contextual_edges",
        postgres_table="mdl_contextual_edges",
        description="All contextual relationships",
        primary_key="edge_id",
        supports_edge_discovery=True
    ),
}


# ============================================================================
# EDGE TYPE PRIORITIES
# ============================================================================

EDGE_TYPE_PRIORITIES: Dict[EdgeType, str] = {
    # Critical Priority
    EdgeType.COLUMN_BELONGS_TO_TABLE: "critical",
    EdgeType.TABLE_BELONGS_TO_CATEGORY: "critical",
    EdgeType.TABLE_RELATES_TO_TABLE: "critical",
    
    # High Priority
    EdgeType.TABLE_HAS_FEATURE: "high",
    EdgeType.FEATURE_SUPPORTS_CONTROL: "high",
    EdgeType.METRIC_FROM_TABLE: "high",
    EdgeType.EXAMPLE_USES_TABLE: "high",
    EdgeType.CATEGORY_BELONGS_TO_PRODUCT: "high",
    
    # Medium Priority
    EdgeType.TABLE_FOLLOWS_INSTRUCTION: "medium",
    EdgeType.INSIGHT_USES_TABLE: "medium",
    EdgeType.BUSINESS_FUNCTION_USES_TABLE: "medium",
    EdgeType.TABLE_HAS_COLUMN: "medium",
    EdgeType.COLUMN_REFERENCES_COLUMN: "medium",
    EdgeType.COLUMN_IS_TIME_DIMENSION: "medium",
    EdgeType.COLUMN_SUPPORTS_KPI: "medium",
    EdgeType.CALCULATED_COLUMN_BELONGS_TO_TABLE: "medium",
    EdgeType.METRIC_USES_COLUMN: "medium",
    EdgeType.FEATURE_USES_TABLE: "medium",
    EdgeType.FEATURE_USES_COLUMN: "medium",
    
    # Low Priority
    EdgeType.OWNERSHIP_FOR_TABLE: "low",
    EdgeType.FRAMEWORK_MAPS_TO_TABLE: "low",
    EdgeType.PRODUCT_HAS_CATEGORY: "low",
    EdgeType.COLUMN_DERIVED_FROM: "low",
    EdgeType.CALCULATED_COLUMN_DERIVED_FROM: "low",
}


# ============================================================================
# QUERY PATTERNS
# ============================================================================

QUERY_PATTERNS: Dict[str, Dict[str, Any]] = {
    "product_discovery": {
        "entity_types": [EntityType.PRODUCT],
        "collections": ["mdl_products"],
        "metadata_filters": ["product_name", "vendor"],
        "description": "Find products by name, vendor, or capabilities"
    },
    
    "category_exploration": {
        "entity_types": [EntityType.CATEGORY],
        "collections": ["mdl_categories"],
        "metadata_filters": ["category_name", "product_id", "business_domain"],
        "description": "Explore categories within a product"
    },
    
    "table_discovery": {
        "entity_types": [EntityType.TABLE],
        "collections": ["mdl_tables"],
        "metadata_filters": ["table_name", "category_id", "product_id", "is_fact_table"],
        "description": "Find tables by name, category, or purpose"
    },
    
    "column_lookup": {
        "entity_types": [EntityType.COLUMN],
        "collections": ["mdl_columns"],
        "metadata_filters": ["column_name", "table_id", "data_type", "is_pii", "is_sensitive_data"],
        "description": "Search columns by name, type, or sensitivity"
    },
    
    "feature_mapping": {
        "entity_types": [EntityType.FEATURE, EntityType.TABLE],
        "collections": ["mdl_features", "mdl_tables"],
        "metadata_filters": ["feature_name", "product_id", "feature_category"],
        "description": "Map features to tables and columns"
    },
    
    "metric_discovery": {
        "entity_types": [EntityType.METRIC, EntityType.TABLE],
        "collections": ["mdl_metrics", "mdl_tables"],
        "metadata_filters": ["metric_name", "metric_type", "aggregation_type"],
        "description": "Find metrics and their calculations"
    },
    
    "example_queries": {
        "entity_types": [EntityType.EXAMPLE],
        "collections": ["mdl_examples"],
        "metadata_filters": ["complexity_level", "use_case"],
        "description": "Find example queries by use case"
    },
    
    "relationship_traversal": {
        "entity_types": [EntityType.RELATIONSHIP, EntityType.EDGE],
        "collections": ["mdl_relationships", "mdl_contextual_edges"],
        "metadata_filters": ["relationship_type", "edge_type", "source_entity_id"],
        "description": "Traverse relationships between entities"
    },
}


# ============================================================================
# CATEGORY DEFINITIONS (15 Categories)
# ============================================================================

MDL_CATEGORIES: List[str] = [
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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_store_mapping(entity_type: EntityType) -> Optional[StoreMapping]:
    """Get store mapping for an entity type"""
    return MDL_STORE_MAPPINGS.get(entity_type)


def get_chroma_collection(entity_type: EntityType) -> Optional[str]:
    """Get ChromaDB collection name for an entity type"""
    mapping = get_store_mapping(entity_type)
    return mapping.chroma_collection if mapping else None


def get_postgres_table(entity_type: EntityType) -> Optional[str]:
    """Get PostgreSQL table name for an entity type"""
    mapping = get_store_mapping(entity_type)
    return mapping.postgres_table if mapping else None


def get_entity_types_for_query_pattern(pattern: str) -> List[EntityType]:
    """Get entity types for a query pattern"""
    pattern_config = QUERY_PATTERNS.get(pattern, {})
    return pattern_config.get("entity_types", [])


def get_collections_for_query_pattern(pattern: str) -> List[str]:
    """Get ChromaDB collections for a query pattern"""
    pattern_config = QUERY_PATTERNS.get(pattern, {})
    return pattern_config.get("collections", [])


def get_edge_priority(edge_type: EdgeType) -> str:
    """Get priority for an edge type"""
    return EDGE_TYPE_PRIORITIES.get(edge_type, "low")


def get_edge_priority_score(edge_type: EdgeType) -> float:
    """Get numeric priority score for an edge type"""
    priority = get_edge_priority(edge_type)
    priority_map = {
        "critical": 1.0,
        "high": 0.8,
        "medium": 0.6,
        "low": 0.4
    }
    return priority_map.get(priority, 0.5)


def is_category_valid(category_name: str) -> bool:
    """Check if a category name is valid"""
    return category_name in MDL_CATEGORIES


def get_all_collections() -> List[str]:
    """Get all ChromaDB collection names"""
    return [mapping.chroma_collection for mapping in MDL_STORE_MAPPINGS.values()]


def get_all_postgres_tables() -> List[str]:
    """Get all PostgreSQL table names"""
    return [mapping.postgres_table for mapping in MDL_STORE_MAPPINGS.values()]


def get_entity_type_from_collection(collection_name: str) -> Optional[EntityType]:
    """Get entity type from ChromaDB collection name"""
    for entity_type, mapping in MDL_STORE_MAPPINGS.items():
        if mapping.chroma_collection == collection_name:
            return entity_type
    return None


def get_entity_type_from_table(table_name: str) -> Optional[EntityType]:
    """Get entity type from PostgreSQL table name"""
    for entity_type, mapping in MDL_STORE_MAPPINGS.items():
        if mapping.postgres_table == table_name:
            return entity_type
    return None


def supports_hybrid_search(entity_type: EntityType) -> bool:
    """Check if entity type supports hybrid search"""
    mapping = get_store_mapping(entity_type)
    return mapping.supports_hybrid_search if mapping else False


def supports_edge_discovery(entity_type: EntityType) -> bool:
    """Check if entity type supports edge discovery"""
    mapping = get_store_mapping(entity_type)
    return mapping.supports_edge_discovery if mapping else False


# Aliases for config/__init__.py
MDLStoreType = EntityType
MDLCollectionConfig = StoreMapping
get_mdl_store_config = get_store_mapping

# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    # Enums
    "EntityType",
    "EdgeType",
    "MDLStoreType",
    
    # Data Classes
    "StoreMapping",
    "MDLCollectionConfig",
    
    # Helper Functions
    "get_mdl_store_config",
    
    # Configurations
    "MDL_STORE_MAPPINGS",
    "EDGE_TYPE_PRIORITIES",
    "QUERY_PATTERNS",
    "MDL_CATEGORIES",
    
    # Helper Functions
    "get_store_mapping",
    "get_chroma_collection",
    "get_postgres_table",
    "get_entity_types_for_query_pattern",
    "get_collections_for_query_pattern",
    "get_edge_priority",
    "get_edge_priority_score",
    "is_category_valid",
    "get_all_collections",
    "get_all_postgres_tables",
    "get_entity_type_from_collection",
    "get_entity_type_from_table",
    "supports_hybrid_search",
    "supports_edge_discovery",
]
