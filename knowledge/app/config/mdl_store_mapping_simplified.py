"""
MDL Store Mapping Configuration (Simplified)

Leverages EXISTING collections with type discriminators instead of creating new collections.
Maps MDL entity types to existing ChromaDB collections and PostgreSQL tables.

Existing Collections Used:
- db_schema - Tables and columns (already indexed by index_mdl_standalone.py)
- table_descriptions - Table descriptions (already indexed)
- column_metadata - Column metadata with time concepts merged in (already indexed)
- entities - Generic entities with type="mdl" and mdl_entity_type discriminator
- evidence - Generic evidence with type="mdl" and mdl_entity_type discriminator
- sql_pairs - SQL examples (already has retrieval: app/agents/data/sql_pairs_retrieval.py)
- instructions - Product instructions (already has retrieval: app/agents/data/instructions.py)
- contextual_edges - All relationship edges
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class MDLEntityType(str, Enum):
    """MDL entity types - mapped to existing collections with discriminators"""
    # Core MDL entities (use existing collections)
    PRODUCT = "product"           # → entities collection, entity_type="mdl", mdl_entity_type="product"
    CATEGORY = "category"         # → entities collection, entity_type="mdl", mdl_entity_type="category"
    TABLE = "table"               # → db_schema / table_descriptions (ALREADY INDEXED)
    COLUMN = "column"             # → db_schema / column_metadata (ALREADY INDEXED)
    RELATIONSHIP = "relationship" # → contextual_edges
    
    # Features and metrics (use entities collection)
    FEATURE = "feature"           # → entities collection, entity_type="mdl", mdl_entity_type="feature"
    METRIC = "metric"             # → entities collection, entity_type="mdl", mdl_entity_type="metric"
    
    # Examples and instructions (use existing collections)
    EXAMPLE = "example"           # → sql_pairs collection (ALREADY HAS RETRIEVAL)
    INSTRUCTION = "instruction"   # → instructions collection (ALREADY HAS RETRIEVAL)
    
    # All edges
    EDGE = "edge"                 # → contextual_edges collection


class MDLEdgeType(str, Enum):
    """MDL edge types with priorities"""
    # Critical Priority - Core schema relationships
    COLUMN_BELONGS_TO_TABLE = "COLUMN_BELONGS_TO_TABLE"
    TABLE_BELONGS_TO_CATEGORY = "TABLE_BELONGS_TO_CATEGORY"
    TABLE_RELATES_TO_TABLE = "TABLE_RELATES_TO_TABLE"
    
    # High Priority - Business relationships
    TABLE_HAS_FEATURE = "TABLE_HAS_FEATURE"
    FEATURE_SUPPORTS_CONTROL = "FEATURE_SUPPORTS_CONTROL"
    METRIC_FROM_TABLE = "METRIC_FROM_TABLE"
    EXAMPLE_USES_TABLE = "EXAMPLE_USES_TABLE"
    CATEGORY_BELONGS_TO_PRODUCT = "CATEGORY_BELONGS_TO_PRODUCT"
    
    # Medium Priority
    TABLE_FOLLOWS_INSTRUCTION = "TABLE_FOLLOWS_INSTRUCTION"
    TABLE_HAS_COLUMN = "TABLE_HAS_COLUMN"
    COLUMN_REFERENCES_COLUMN = "COLUMN_REFERENCES_COLUMN"
    COLUMN_HAS_TIME_CONCEPT = "COLUMN_HAS_TIME_CONCEPT"  # Time concepts merged into column
    COLUMN_SUPPORTS_METRIC = "COLUMN_SUPPORTS_METRIC"
    METRIC_USES_COLUMN = "METRIC_USES_COLUMN"
    FEATURE_USES_TABLE = "FEATURE_USES_TABLE"
    FEATURE_USES_COLUMN = "FEATURE_USES_COLUMN"
    
    # Low Priority
    PRODUCT_HAS_CATEGORY = "PRODUCT_HAS_CATEGORY"


@dataclass
class SimplifiedStoreMapping:
    """Simplified mapping using existing collections"""
    entity_type: MDLEntityType
    chroma_collection: str
    postgres_table: str
    description: str
    metadata_discriminator: Optional[Dict[str, str]] = None  # For type filtering
    retrieval_available: bool = False  # Has existing retrieval code


# ============================================================================
# SIMPLIFIED STORE MAPPINGS (Uses Existing Collections)
# ============================================================================

MDL_SIMPLIFIED_MAPPINGS: Dict[MDLEntityType, SimplifiedStoreMapping] = {
    # Products and Categories → entities collection with type discriminator
    MDLEntityType.PRODUCT: SimplifiedStoreMapping(
        entity_type=MDLEntityType.PRODUCT,
        chroma_collection="entities",
        postgres_table="entities",  # Or create mdl_products if needed
        description="Product definitions (Snyk, Cornerstone)",
        metadata_discriminator={"entity_type": "mdl", "mdl_entity_type": "product"},
        retrieval_available=False
    ),
    
    MDLEntityType.CATEGORY: SimplifiedStoreMapping(
        entity_type=MDLEntityType.CATEGORY,
        chroma_collection="entities",
        postgres_table="entities",  # Or create mdl_categories if needed
        description="15 business categories",
        metadata_discriminator={"entity_type": "mdl", "mdl_entity_type": "category"},
        retrieval_available=False
    ),
    
    # Tables → EXISTING db_schema and table_descriptions collections
    MDLEntityType.TABLE: SimplifiedStoreMapping(
        entity_type=MDLEntityType.TABLE,
        chroma_collection="table_descriptions",  # ALREADY INDEXED by index_mdl_standalone
        postgres_table="table_descriptions",     # Or use existing schema
        description="Table schemas and descriptions (ALREADY INDEXED)",
        metadata_discriminator={"product_name": "$PRODUCT", "project_id": "$PROJECT"},
        retrieval_available=True  # Already has retrieval in retrieval.py
    ),
    
    # Columns → EXISTING db_schema and column_metadata collections
    MDLEntityType.COLUMN: SimplifiedStoreMapping(
        entity_type=MDLEntityType.COLUMN,
        chroma_collection="column_metadata",     # ALREADY INDEXED by index_mdl_standalone
        postgres_table="column_metadata",        # Or use existing schema
        description="Column metadata with time concepts merged (ALREADY INDEXED)",
        metadata_discriminator={"product_name": "$PRODUCT", "project_id": "$PROJECT"},
        retrieval_available=True  # Already has retrieval
    ),
    
    # Relationships → contextual_edges collection
    MDLEntityType.RELATIONSHIP: SimplifiedStoreMapping(
        entity_type=MDLEntityType.RELATIONSHIP,
        chroma_collection="contextual_edges",
        postgres_table="contextual_relationships",  # Existing table
        description="Table relationships and foreign keys",
        metadata_discriminator={"edge_type": "TABLE_RELATES_TO_TABLE"},
        retrieval_available=True
    ),
    
    # Features → entities collection with type discriminator
    MDLEntityType.FEATURE: SimplifiedStoreMapping(
        entity_type=MDLEntityType.FEATURE,
        chroma_collection="entities",
        postgres_table="entities",
        description="Product features",
        metadata_discriminator={"entity_type": "mdl", "mdl_entity_type": "feature"},
        retrieval_available=False
    ),
    
    # Metrics → entities collection with type discriminator
    MDLEntityType.METRIC: SimplifiedStoreMapping(
        entity_type=MDLEntityType.METRIC,
        chroma_collection="entities",
        postgres_table="entities",
        description="Business metrics and KPIs",
        metadata_discriminator={"entity_type": "mdl", "mdl_entity_type": "metric"},
        retrieval_available=False
    ),
    
    # Examples → EXISTING sql_pairs collection
    MDLEntityType.EXAMPLE: SimplifiedStoreMapping(
        entity_type=MDLEntityType.EXAMPLE,
        chroma_collection="sql_pairs",           # ALREADY HAS RETRIEVAL
        postgres_table="sql_pairs",
        description="SQL examples and natural questions (ALREADY HAS RETRIEVAL)",
        metadata_discriminator={"project_id": "$PROJECT"},
        retrieval_available=True  # app/agents/data/sql_pairs_retrieval.py
    ),
    
    # Instructions → EXISTING instructions collection
    MDLEntityType.INSTRUCTION: SimplifiedStoreMapping(
        entity_type=MDLEntityType.INSTRUCTION,
        chroma_collection="instructions",        # ALREADY HAS RETRIEVAL
        postgres_table="instructions",
        description="Product instructions and best practices (ALREADY HAS RETRIEVAL)",
        metadata_discriminator={"project_id": "$PROJECT"},
        retrieval_available=True  # app/agents/data/instructions.py
    ),
    
    # All edges → contextual_edges collection
    MDLEntityType.EDGE: SimplifiedStoreMapping(
        entity_type=MDLEntityType.EDGE,
        chroma_collection="contextual_edges",
        postgres_table="contextual_relationships",
        description="All contextual relationships between entities",
        metadata_discriminator=None,
        retrieval_available=True
    ),
}


# ============================================================================
# 15 BUSINESS CATEGORIES (from FINAL_CATEGORIES.md)
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
# EDGE TYPE PRIORITIES
# ============================================================================

EDGE_TYPE_PRIORITIES: Dict[MDLEdgeType, str] = {
    # Critical Priority
    MDLEdgeType.COLUMN_BELONGS_TO_TABLE: "critical",
    MDLEdgeType.TABLE_BELONGS_TO_CATEGORY: "critical",
    MDLEdgeType.TABLE_RELATES_TO_TABLE: "critical",
    
    # High Priority
    MDLEdgeType.TABLE_HAS_FEATURE: "high",
    MDLEdgeType.FEATURE_SUPPORTS_CONTROL: "high",
    MDLEdgeType.METRIC_FROM_TABLE: "high",
    MDLEdgeType.EXAMPLE_USES_TABLE: "high",
    MDLEdgeType.CATEGORY_BELONGS_TO_PRODUCT: "high",
    
    # Medium Priority
    MDLEdgeType.TABLE_FOLLOWS_INSTRUCTION: "medium",
    MDLEdgeType.TABLE_HAS_COLUMN: "medium",
    MDLEdgeType.COLUMN_REFERENCES_COLUMN: "medium",
    MDLEdgeType.COLUMN_HAS_TIME_CONCEPT: "medium",
    MDLEdgeType.COLUMN_SUPPORTS_METRIC: "medium",
    MDLEdgeType.METRIC_USES_COLUMN: "medium",
    MDLEdgeType.FEATURE_USES_TABLE: "medium",
    MDLEdgeType.FEATURE_USES_COLUMN: "medium",
    
    # Low Priority
    MDLEdgeType.PRODUCT_HAS_CATEGORY: "low",
}


# ============================================================================
# QUERY PATTERNS (Updated for existing collections)
# ============================================================================

SIMPLIFIED_QUERY_PATTERNS: Dict[str, Dict[str, Any]] = {
    "table_discovery": {
        "collections": ["table_descriptions"],  # Use existing collection
        "metadata_filters": ["product_name", "project_id", "category_name"],
        "retrieval_available": True,
        "description": "Find tables by semantic description (ALREADY INDEXED)"
    },
    
    "column_lookup": {
        "collections": ["column_metadata"],  # Use existing collection
        "metadata_filters": ["product_name", "project_id", "table_name", "is_pii"],
        "retrieval_available": True,
        "description": "Search columns with time concepts merged (ALREADY INDEXED)"
    },
    
    "category_exploration": {
        "collections": ["entities"],  # Use entities with discriminator
        "metadata_filters": ["entity_type", "mdl_entity_type", "product_name"],
        "retrieval_available": False,
        "description": "Explore 15 business categories"
    },
    
    "feature_mapping": {
        "collections": ["entities"],  # Use entities with discriminator
        "metadata_filters": ["entity_type", "mdl_entity_type", "product_name"],
        "retrieval_available": False,
        "description": "Map features to tables"
    },
    
    "metric_discovery": {
        "collections": ["entities"],  # Use entities with discriminator
        "metadata_filters": ["entity_type", "mdl_entity_type", "product_name"],
        "retrieval_available": False,
        "description": "Find metrics and KPIs"
    },
    
    "example_queries": {
        "collections": ["sql_pairs"],  # Use existing collection
        "metadata_filters": ["project_id"],
        "retrieval_available": True,  # app/agents/data/sql_pairs_retrieval.py
        "description": "Find SQL examples (ALREADY HAS RETRIEVAL)"
    },
    
    "instruction_lookup": {
        "collections": ["instructions"],  # Use existing collection
        "metadata_filters": ["project_id"],
        "retrieval_available": True,  # app/agents/data/instructions.py
        "description": "Get product instructions (ALREADY HAS RETRIEVAL)"
    },
    
    "relationship_traversal": {
        "collections": ["contextual_edges"],
        "metadata_filters": ["edge_type", "source_entity_id", "target_entity_id"],
        "retrieval_available": True,
        "description": "Traverse relationships via contextual edges"
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_simplified_mapping(entity_type: MDLEntityType) -> Optional[SimplifiedStoreMapping]:
    """Get simplified store mapping for an entity type"""
    return MDL_SIMPLIFIED_MAPPINGS.get(entity_type)


def get_chroma_collection(entity_type: MDLEntityType) -> Optional[str]:
    """Get ChromaDB collection name for an entity type"""
    mapping = get_simplified_mapping(entity_type)
    return mapping.chroma_collection if mapping else None


def get_postgres_table(entity_type: MDLEntityType) -> Optional[str]:
    """Get PostgreSQL table name for an entity type"""
    mapping = get_simplified_mapping(entity_type)
    return mapping.postgres_table if mapping else None


def get_metadata_discriminator(entity_type: MDLEntityType) -> Optional[Dict[str, str]]:
    """Get metadata discriminator for filtering in shared collections"""
    mapping = get_simplified_mapping(entity_type)
    return mapping.metadata_discriminator if mapping else None


def has_existing_retrieval(entity_type: MDLEntityType) -> bool:
    """Check if entity type has existing retrieval code"""
    mapping = get_simplified_mapping(entity_type)
    return mapping.retrieval_available if mapping else False


def get_edge_priority(edge_type: MDLEdgeType) -> str:
    """Get priority for an edge type"""
    return EDGE_TYPE_PRIORITIES.get(edge_type, "low")


def get_edge_priority_score(edge_type: MDLEdgeType) -> float:
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


def build_entity_filter(
    entity_type: MDLEntityType,
    product_name: Optional[str] = None,
    project_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Build metadata filter for querying entities in shared collections.
    
    Args:
        entity_type: The MDL entity type
        product_name: Optional product name filter
        project_id: Optional project ID filter
        **kwargs: Additional filters
    
    Returns:
        Dictionary of metadata filters
    """
    mapping = get_simplified_mapping(entity_type)
    if not mapping:
        return {}
    
    filters = {}
    
    # Add discriminator filters
    if mapping.metadata_discriminator:
        for key, value in mapping.metadata_discriminator.items():
            if value.startswith("$"):
                # Placeholder - replace with actual value
                if value == "$PRODUCT" and product_name:
                    filters[key] = product_name
                elif value == "$PROJECT" and project_id:
                    filters[key] = project_id
            else:
                filters[key] = value
    
    # Add additional filters
    if product_name and "product_name" not in filters:
        filters["product_name"] = product_name
    if project_id and "project_id" not in filters:
        filters["project_id"] = project_id
    
    # Add any extra filters
    filters.update(kwargs)
    
    return filters


def get_collections_for_pattern(pattern_name: str) -> List[str]:
    """Get collections for a query pattern"""
    pattern = SIMPLIFIED_QUERY_PATTERNS.get(pattern_name, {})
    return pattern.get("collections", [])


# ============================================================================
# SUMMARY OF WHAT'S ALREADY AVAILABLE
# ============================================================================

ALREADY_INDEXED = {
    "collections": [
        "db_schema",           # Tables and columns (index_mdl_standalone.py)
        "table_descriptions",  # Table descriptions (index_mdl_standalone.py)
        "column_metadata",     # Column metadata (index_mdl_standalone.py)
    ],
    "retrievals": [
        "sql_pairs",          # app/agents/data/sql_pairs_retrieval.py
        "instructions",       # app/agents/data/instructions.py
    ],
    "notes": [
        "Time concepts can be merged into column_metadata",
        "Calculated columns supported in db_schema",
        "Relationships can use contextual_edges",
        "Use entities collection with type discriminators for new entity types",
        "Use evidence collection with type discriminators for MDL evidence"
    ]
}


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    # Enums
    "MDLEntityType",
    "MDLEdgeType",
    
    # Data Classes
    "SimplifiedStoreMapping",
    
    # Configurations
    "MDL_SIMPLIFIED_MAPPINGS",
    "EDGE_TYPE_PRIORITIES",
    "SIMPLIFIED_QUERY_PATTERNS",
    "MDL_CATEGORIES",
    "ALREADY_INDEXED",
    
    # Helper Functions
    "get_simplified_mapping",
    "get_chroma_collection",
    "get_postgres_table",
    "get_metadata_discriminator",
    "has_existing_retrieval",
    "get_edge_priority",
    "get_edge_priority_score",
    "is_category_valid",
    "build_entity_filter",
    "get_collections_for_pattern",
]
