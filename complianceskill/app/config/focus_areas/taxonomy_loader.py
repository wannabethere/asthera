"""
Loader for the framework-agnostic focus area taxonomy.

This taxonomy maps user queries to cybersecurity focus areas that are then
mapped to framework-specific controls, metric categories, and data source capabilities.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Path to taxonomy file (it's in the parent config directory, not in focus_areas subdirectory)
_TAXONOMY_FILE = Path(__file__).parent.parent / "focus_area_taxonomy.json"

# Cache for loaded taxonomy
_TAXONOMY: Optional[Dict[str, Any]] = None


def load_taxonomy() -> Dict[str, Any]:
    """
    Load the focus area taxonomy.
    
    Returns:
        Taxonomy dict with focus_areas mapping
    """
    global _TAXONOMY
    
    if _TAXONOMY is not None:
        return _TAXONOMY
    
    if not _TAXONOMY_FILE.exists():
        logger.warning(f"Focus area taxonomy file not found: {_TAXONOMY_FILE}")
        return {"focus_areas": {}}
    
    try:
        with open(_TAXONOMY_FILE, "r") as f:
            _TAXONOMY = json.load(f)
        logger.debug(f"Loaded focus area taxonomy: {len(_TAXONOMY.get('focus_areas', {}))} focus areas")
        return _TAXONOMY
    except Exception as e:
        logger.error(f"Error loading focus area taxonomy: {e}", exc_info=True)
        return {"focus_areas": {}}


def get_taxonomy_focus_areas() -> Dict[str, Dict[str, Any]]:
    """
    Get all focus areas from the taxonomy.
    
    Returns:
        Dict mapping focus area ID to focus area definition
    """
    taxonomy = load_taxonomy()
    return taxonomy.get("focus_areas", {})


def get_focus_area_by_id(focus_area_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific focus area from the taxonomy by ID.
    
    Args:
        focus_area_id: Focus area ID (e.g., "vulnerability_management")
    
    Returns:
        Focus area definition or None if not found
    """
    focus_areas = get_taxonomy_focus_areas()
    return focus_areas.get(focus_area_id)


def get_focus_areas_by_framework(framework_id: str) -> List[str]:
    """
    Get focus area IDs that map to a specific framework.
    
    Args:
        framework_id: Framework ID (e.g., "soc2", "hipaa")
    
    Returns:
        List of focus area IDs
    """
    focus_areas = get_taxonomy_focus_areas()
    framework_key = f"{framework_id}_controls"
    
    matching_ids = []
    for fa_id, fa_def in focus_areas.items():
        if framework_key in fa_def and fa_def[framework_key]:
            matching_ids.append(fa_id)
    
    return matching_ids


def get_focus_areas_by_source_capability(source_capability: str) -> List[str]:
    """
    Get focus area IDs that match a source capability pattern.
    
    Args:
        source_capability: Source capability (e.g., "qualys.vulnerabilities")
    
    Returns:
        List of focus area IDs
    """
    focus_areas = get_taxonomy_focus_areas()
    
    matching_ids = []
    for fa_id, fa_def in focus_areas.items():
        patterns = fa_def.get("source_capabilities_pattern", [])
        for pattern in patterns:
            # Simple pattern matching (supports wildcards)
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if source_capability.startswith(prefix):
                    matching_ids.append(fa_id)
                    break
            elif pattern == source_capability:
                matching_ids.append(fa_id)
                break
    
    return matching_ids


def map_taxonomy_to_data_source_focus_areas(
    taxonomy_focus_area_ids: List[str],
    data_source_focus_areas: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Map taxonomy focus areas to data-source-specific focus areas.
    
    This matches taxonomy focus areas (e.g., "vulnerability_management") to
    data-source-specific focus areas (e.g., qualys "vulnerability_management").
    
    Args:
        taxonomy_focus_area_ids: List of taxonomy focus area IDs
        data_source_focus_areas: List of data-source-specific focus area dicts
    
    Returns:
        List of matched data-source-specific focus areas
    """
    matched = []
    taxonomy = get_taxonomy_focus_areas()
    
    for taxonomy_id in taxonomy_focus_area_ids:
        # Try to find matching data-source focus area by ID
        for ds_fa in data_source_focus_areas:
            if ds_fa.get("id") == taxonomy_id:
                matched.append(ds_fa)
                break
        
        # If no exact match, try matching by categories
        taxonomy_fa = taxonomy.get(taxonomy_id, {})
        taxonomy_categories = set(taxonomy_fa.get("metric_categories", []))
        
        if not matched or matched[-1].get("id") != taxonomy_id:
            # Look for data-source focus areas with matching categories
            for ds_fa in data_source_focus_areas:
                ds_categories = set(ds_fa.get("categories", []))
                if taxonomy_categories & ds_categories:  # Intersection
                    if ds_fa not in matched:
                        matched.append(ds_fa)
    
    return matched
