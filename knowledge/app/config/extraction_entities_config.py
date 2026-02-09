"""
Extraction Entities Config
Loads doc_types, domains, and store mapping from kb-dump-utility config
(extractions.json + knowledge_assistant_mapping.json) for context breakdown prompts.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CACHE: Optional[Tuple[Dict[str, Any], Dict[str, Any]]] = None


def _load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None or not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load %s: %s", path, e)
        return None


def get_extraction_config_paths() -> Tuple[Optional[Path], Optional[Path]]:
    """
    Resolve paths to extractions.json and knowledge_assistant_mapping.json.
    Uses env KB_DUMP_EXTRACTIONS_PATH, KB_DUMP_MAPPING_PATH, or KB_DUMP_CONFIG_DIR (directory).
    """
    extractions_path = os.environ.get("KB_DUMP_EXTRACTIONS_PATH")
    mapping_path = os.environ.get("KB_DUMP_MAPPING_PATH")
    config_dir = os.environ.get("KB_DUMP_CONFIG_DIR")

    if extractions_path:
        ex = Path(extractions_path)
    elif config_dir:
        ex = Path(config_dir) / "extractions.json"
    else:
        ex = None

    if mapping_path:
        mp = Path(mapping_path)
    elif config_dir:
        mp = Path(config_dir) / "knowledge_assistant_mapping.json"
    else:
        mp = None

    return (ex if ex and ex.exists() else None, mp if mp and mp.exists() else None)


def load_extraction_entities_config(
    extractions_path: Optional[Path] = None,
    mapping_path: Optional[Path] = None,
    use_cache: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Load extractions.json and knowledge_assistant_mapping.json.
    Returns (extractions_data, mapping_data). Either can be None if not found.
    """
    global _CACHE
    if use_cache and _CACHE is not None:
        return _CACHE

    if extractions_path is None and mapping_path is None:
        ex_path, map_path = get_extraction_config_paths()
        extractions_path = ex_path
        mapping_path = map_path

    extractions = _load_json(extractions_path) if extractions_path else None
    mapping = _load_json(mapping_path) if mapping_path else None

    if use_cache:
        _CACHE = (extractions, mapping)
    return (extractions, mapping)


def get_doc_types(extractions: Optional[Dict[str, Any]] = None) -> List[str]:
    """Return doc_types list from extractions.json taxonomies."""
    if extractions is None:
        ex, _ = load_extraction_entities_config(use_cache=True)
        extractions = ex
    if not extractions or "taxonomies" not in extractions:
        return []
    return list(extractions["taxonomies"].get("doc_types", []))


def get_domains(extractions: Optional[Dict[str, Any]] = None) -> List[str]:
    """Return domains list from extractions.json taxonomies."""
    if extractions is None:
        ex, _ = load_extraction_entities_config(use_cache=True)
        extractions = ex
    if not extractions or "taxonomies" not in extractions:
        return []
    return list(extractions["taxonomies"].get("domains", []))


def get_doc_type_to_store(
    mapping: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, str]]:
    """
    Return doc_type -> { store_name, metadata_type, extraction_type } from
    knowledge_assistant_mapping.json doc_type_to_store.
    """
    if mapping is None:
        _, mapping = load_extraction_entities_config(use_cache=True)
    if not mapping or "doc_type_to_store" not in mapping:
        return {}
    return dict(mapping["doc_type_to_store"])


def get_identifier_entity_types(extractions: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Return pattern identifier name -> entity_type from extractions patterns.identifiers."""
    if extractions is None:
        ex, _ = load_extraction_entities_config(use_cache=True)
        extractions = ex
    out = {}
    if not extractions or "patterns" not in extractions or "identifiers" not in extractions["patterns"]:
        return out
    for name, cfg in extractions["patterns"]["identifiers"].items():
        if isinstance(cfg, dict) and "entity_type" in cfg:
            out[name] = cfg["entity_type"]
    return out
