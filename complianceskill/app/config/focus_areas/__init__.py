"""
Focus Area Catalog Loader

Loads static focus area catalogs by data source for compliance workflow.
Focus areas are deterministic mappings from framework + data source capabilities.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Path to focus area catalog files
_FOCUS_AREAS_DIR = Path(__file__).parent

# Cache for loaded catalogs
_LOADED_CATALOGS: Dict[str, Dict[str, Any]] = {}


def load_focus_areas_catalog(data_source: str) -> Optional[Dict[str, Any]]:
    """
    Load focus areas catalog for a data source.
    
    Args:
        data_source: Data source identifier (e.g., "qualys", "sentinel", "snyk", "wiz")
    
    Returns:
        Focus areas catalog dict or None if not found
    """
    if data_source in _LOADED_CATALOGS:
        return _LOADED_CATALOGS[data_source]
    
    catalog_path = _FOCUS_AREAS_DIR / f"{data_source}_focus_areas.json"
    
    if not catalog_path.exists():
        logger.warning(f"Focus areas catalog not found for data source: {data_source}")
        return None
    
    try:
        with open(catalog_path, "r") as f:
            catalog = json.load(f)
        _LOADED_CATALOGS[data_source] = catalog
        logger.debug(f"Loaded focus areas catalog for {data_source}: {len(catalog.get('focus_areas', []))} focus areas")
        return catalog
    except Exception as e:
        logger.error(f"Error loading focus areas catalog for {data_source}: {e}", exc_info=True)
        return None


def get_focus_areas_by_data_source(data_source: str) -> List[Dict[str, Any]]:
    """
    Get list of focus areas for a data source.
    
    Args:
        data_source: Data source identifier
    
    Returns:
        List of focus area dicts
    """
    catalog = load_focus_areas_catalog(data_source)
    if not catalog:
        return []
    return catalog.get("focus_areas", [])


def get_focus_areas_by_framework(
    data_source: str,
    framework_id: str
) -> List[Dict[str, Any]]:
    """
    Get focus areas for a data source filtered by framework.
    
    Args:
        data_source: Data source identifier
        framework_id: Framework ID (e.g., "soc2", "hipaa", "nist_csf", "iso27001")
    
    Returns:
        List of focus area dicts that support the framework
    """
    focus_areas = get_focus_areas_by_data_source(data_source)
    
    # Filter focus areas that have mappings for this framework
    filtered = []
    for fa in focus_areas:
        framework_mappings = fa.get("framework_mappings", {})
        if framework_id in framework_mappings:
            filtered.append(fa)
    
    return filtered


def get_focus_area_by_id(
    data_source: str,
    focus_area_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific focus area by ID.
    
    Args:
        data_source: Data source identifier
        focus_area_id: Focus area ID
    
    Returns:
        Focus area dict or None if not found
    """
    focus_areas = get_focus_areas_by_data_source(data_source)
    for fa in focus_areas:
        if fa.get("id") == focus_area_id:
            return fa
    return None


def get_focus_areas_by_category(
    data_source: str,
    category: str
) -> List[Dict[str, Any]]:
    """
    Get focus areas for a data source filtered by category.
    
    Args:
        data_source: Data source identifier
        category: Category name (e.g., "vulnerabilities", "access_control")
    
    Returns:
        List of focus area dicts that include this category
    """
    focus_areas = get_focus_areas_by_data_source(data_source)
    
    filtered = []
    for fa in focus_areas:
        categories = fa.get("categories", [])
        if category in categories:
            filtered.append(fa)
    
    return filtered


def get_all_supported_data_sources() -> List[str]:
    """
    Get list of all data sources with focus area catalogs.
    
    Returns:
        List of data source identifiers
    """
    data_sources = []
    for catalog_file in _FOCUS_AREAS_DIR.glob("*_focus_areas.json"):
        # Extract data source from filename: "{data_source}_focus_areas.json"
        data_source = catalog_file.stem.replace("_focus_areas", "")
        data_sources.append(data_source)
    return data_sources
