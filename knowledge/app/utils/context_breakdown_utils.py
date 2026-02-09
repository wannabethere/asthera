"""
Utility functions for ContextBreakdown conversions

Provides helpers to:
1. Convert ContextBreakdown dataclass to dict (for state storage)
2. Extract fields from either dataclass or dict (for backward compatibility)
"""
from typing import Any, Optional
from dataclasses import asdict, is_dataclass


def breakdown_to_dict(breakdown: Any) -> dict:
    """
    Convert a ContextBreakdown dataclass to a dict, or return dict as-is.
    
    Args:
        breakdown: ContextBreakdown dataclass or dict
        
    Returns:
        Dict representation of the breakdown
    """
    if breakdown is None:
        return {}
    
    # If it's already a dict, return as-is
    if isinstance(breakdown, dict):
        return breakdown
    
    # If it's a dataclass, convert to dict
    if is_dataclass(breakdown):
        return asdict(breakdown)
    
    # If it has a to_dict method, use it
    if hasattr(breakdown, 'to_dict'):
        return breakdown.to_dict()
    
    # Otherwise, try to convert to dict via __dict__
    if hasattr(breakdown, '__dict__'):
        return vars(breakdown)
    
    # Fallback: return empty dict
    return {}


def get_breakdown_field(breakdown: Any, field_name: str, default: Any = None) -> Any:
    """
    Extract a field from either a ContextBreakdown dataclass or dict.
    
    This helper provides backward compatibility between:
    - New ContextBreakdown dataclass (from app.agents.contextual_agents)
    - Old dict-based breakdowns (from legacy implementations)
    
    Args:
        breakdown: Either a ContextBreakdown dataclass or dict
        field_name: Name of the field to extract
        default: Default value if field not found
        
    Returns:
        Field value or default
        
    Examples:
        >>> # Works with dataclass
        >>> from app.agents.contextual_agents.base_context_breakdown_agent import ContextBreakdown
        >>> breakdown = ContextBreakdown(user_question="test", query_type="mdl")
        >>> get_breakdown_field(breakdown, 'query_type', 'unknown')
        'mdl'
        
        >>> # Works with dict
        >>> breakdown = {'query_type': 'mdl', 'identified_entities': ['entity1']}
        >>> get_breakdown_field(breakdown, 'query_type', 'unknown')
        'mdl'
    """
    if breakdown is None:
        return default
    
    # Try dataclass attribute access first
    if hasattr(breakdown, field_name):
        return getattr(breakdown, field_name, default)
    
    # Fall back to dict access
    if isinstance(breakdown, dict):
        return breakdown.get(field_name, default)
    
    return default


def normalize_breakdown_for_state(breakdown: Any) -> dict:
    """
    Normalize a breakdown for storage in LangGraph state.
    
    LangGraph TypedDict states expect dicts, not dataclasses.
    This function converts ContextBreakdown dataclass to dict if needed.
    
    Args:
        breakdown: ContextBreakdown dataclass or dict
        
    Returns:
        Dict suitable for state storage
        
    Example:
        >>> from app.agents.contextual_agents.base_context_breakdown_agent import ContextBreakdown
        >>> breakdown = ContextBreakdown(user_question="test", query_type="mdl")
        >>> state = {}
        >>> state['generic_breakdown'] = normalize_breakdown_for_state(breakdown)
        >>> # Now state['generic_breakdown'] is a dict that can be stored in TypedDict state
    """
    result = breakdown_to_dict(breakdown)
    
    # Ensure all required fields are present (with defaults if missing)
    defaults = {
        'query_type': 'unknown',
        'identified_entities': [],
        'entity_types': [],
        'edge_types': [],
        'query_keywords': [],
        'entity_sub_types': [],
        'evidence_gathering_required': False,
        'evidence_types_needed': [],
        'data_retrieval_plan': [],
        'metrics_kpis_needed': [],
        'frameworks': []
    }
    
    for key, default_value in defaults.items():
        if key not in result:
            result[key] = default_value
    
    return result
