"""
CSOD MDL Utilities

Utility functions for MDL (Metadata Layer) operations, including column pruning
and schema manipulation. Reuses DT utilities but can be extended for CSOD-specific needs.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def prune_columns_from_schemas(
    schemas: List[Dict[str, Any]],
    user_query: str,
    reasoning: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Prune columns from MDL schemas based on user query and optional reasoning.
    
    Reuses the DT implementation but can be customized for CSOD-specific needs.
    """
    from app.agents.dt_mdl_utils import prune_columns_from_schemas as dt_prune_columns
    
    return dt_prune_columns(
        schemas=schemas,
        user_query=user_query,
        reasoning=reasoning
    )
