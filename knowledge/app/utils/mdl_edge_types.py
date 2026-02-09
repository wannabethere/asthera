"""
MDL Edge Type Definitions and Utilities

DEPRECATED: Core models have been moved to app/models/mdl.py
This file now re-exports models for backward compatibility.
All utility functions remain here.
"""
from typing import Dict, List, Any, Tuple
from app.models.mdl import (
    MDLEntityType,
    MDLEdgeType,
    MDLEdgeTypeDefinition,
    MDL_EDGE_TYPE_DEFINITIONS,
    get_mdl_edge_type_semantics,
    get_edge_type_priority,
    validate_mdl_edge,
    get_edge_types_by_priority,
    get_edge_types_for_entity,
    get_mdl_categories,
)

# Re-export all models and functions for backward compatibility
__all__ = [
    # Types
    "MDLEntityType",
    "MDLEdgeType",
    "MDLEdgeTypeDefinition",
    
    # Constants
    "MDL_EDGE_TYPE_DEFINITIONS",
    
    # Functions
    "get_mdl_edge_type_semantics",
    "get_edge_type_priority",
    "validate_mdl_edge",
    "get_edge_types_by_priority",
    "get_edge_types_for_entity",
    "get_mdl_categories",
]
