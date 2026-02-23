"""
Breakdown Entities Loader
Loads breakdown_entities_config.yaml and returns a short markdown block (~10-15 sentences)
for use in generic context breakdown prompts. MDL-specific entities stay in mdl_prompts.
Also provides entity -> collection mapping so retrieval can resolve planner entity types
to the collection (store) to query.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "breakdown_entities_config.yaml"
_CACHE: Optional[str] = None
_ENTITY_TO_COLLECTION_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _load_yaml(path: Path) -> Optional[Dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed; breakdown_entities_config.yaml will not be loaded")
        return None
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to load breakdown_entities_config.yaml: %s", e)
        return None


def _generate_summary_from_entities(entities: Dict[str, Any]) -> List[str]:
    """Build ~10-15 sentences from structured entities when summary.sentences is not provided."""
    sentences: List[str] = []
    doc_types = entities.get("doc_types") or []
    if doc_types:
        sentences.append(
            "Doc types (taxonomy) are: " + ", ".join(doc_types) + "."
        )
    domains = entities.get("domains") or []
    if domains:
        sentences.append(
            "Domains (for context) include: " + ", ".join(domains) + "."
        )
    stores = entities.get("stores") or {}
    for store_name, info in stores.items():
        if isinstance(info, dict) and info.get("description"):
            sentences.append(f"{store_name}: {info['description']}")
    doc_type_to_store = entities.get("doc_type_to_store") or {}
    if doc_type_to_store:
        by_store: Dict[str, List[str]] = {}
        for doc_type, mapping in doc_type_to_store.items():
            if isinstance(mapping, dict):
                store = mapping.get("store", "")
                if store not in by_store:
                    by_store[store] = []
                by_store[store].append(doc_type)
        if by_store:
            parts = [f"{store} ({', '.join(dts)})" for store, dts in sorted(by_store.items())]
            sentences.append("Doc type to store: " + "; ".join(parts) + ".")
    return sentences[:15]


def get_breakdown_entities_markdown(config_path: Optional[Path] = None) -> str:
    """
    Load breakdown_entities_config.yaml and return a short markdown block (~10-15 sentences)
    for the generic breakdown prompt. Returns empty string if config is missing or invalid.
    """
    global _CACHE
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        return ""

    data = _load_yaml(path)
    if not data:
        return ""

    summary = data.get("summary") or {}
    sentences = summary.get("sentences")
    if isinstance(sentences, list) and len(sentences) > 0:
        lines = [s.strip() for s in sentences if isinstance(s, str) and s.strip()]
    else:
        entities = data.get("entities") or {}
        lines = _generate_summary_from_entities(entities)

    if not lines:
        return ""

    block = "## Available Entities (from config)\n\n"
    block += "Use only these entities and stores for context breakdown. Filter by type/framework as described.\n\n"
    block += "\n".join(f"- {s}" for s in lines)
    # Append entity-to-collection note so planner uses only entity types that map to retrievable collections
    mapping = data.get("entity_to_collection") or {}
    if mapping:
        known = sorted(str(k) for k in mapping.keys() if k)
        block += "\n\n**Entity names in search_questions must be from this list (they map to collections for retrieval):** "
        block += ", ".join(known) + "."
    return block.strip()


def get_breakdown_entities_markdown_cached(
    config_path: Optional[Path] = None,
    use_cache: bool = True,
) -> str:
    """Same as get_breakdown_entities_markdown but with optional caching."""
    global _CACHE
    if use_cache and _CACHE is not None:
        return _CACHE
    result = get_breakdown_entities_markdown(config_path)
    if use_cache:
        _CACHE = result
    return result


def clear_breakdown_entities_cache() -> None:
    """Clear the cached markdown and entity-to-collection mapping (e.g. after config change)."""
    global _CACHE, _ENTITY_TO_COLLECTION_CACHE
    _CACHE = None
    _ENTITY_TO_COLLECTION_CACHE = None


def get_entity_to_collection_mapping(config_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load entity_to_collection from breakdown_entities_config.yaml.
    Returns dict: entity_type -> { "collection": str, "default_metadata": dict (optional) }.
    Used by retrieval to map planner entity types to the collection (store) to query.
    """
    global _ENTITY_TO_COLLECTION_CACHE
    if _ENTITY_TO_COLLECTION_CACHE is not None:
        return _ENTITY_TO_COLLECTION_CACHE
    path = config_path or _DEFAULT_CONFIG_PATH
    data = _load_yaml(path)
    mapping = {}
    if data and "entity_to_collection" in data:
        raw = data["entity_to_collection"] or {}
        for entity_name, info in raw.items():
            if not isinstance(info, dict):
                continue
            collection = info.get("collection")
            if not collection:
                continue
            entry = {"collection": str(collection)}
            default_meta = info.get("default_metadata")
            if isinstance(default_meta, dict):
                entry["default_metadata"] = dict(default_meta)
            mapping[str(entity_name).strip()] = entry
    _ENTITY_TO_COLLECTION_CACHE = mapping
    return mapping


def resolve_entity_to_collection(
    entity: str,
    config_path: Optional[Path] = None,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Resolve a planner entity type to the collection name and default metadata for retrieval.
    Returns (collection_name, default_metadata). collection_name is None if entity is unknown.
    """
    mapping = get_entity_to_collection_mapping(config_path)
    entity_key = str(entity).strip() if entity else ""
    if not entity_key:
        return None, {}
    entry = mapping.get(entity_key)
    if not entry:
        logger.debug("Entity '%s' not in entity_to_collection config; cannot resolve to collection", entity_key)
        return None, {}
    return entry.get("collection"), entry.get("default_metadata", {})


def resolve_search_question_to_collection(
    search_question: Dict[str, Any],
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Resolve a search_question (from planner) to the collection and merged metadata for retrieval.
    search_question should have: entity, question, metadata_filters (optional), response_type (optional).
    Returns dict with: collection (str or None), question, metadata_filters (merged with default_metadata),
    response_type, entity (original). If entity is unknown, collection is None and metadata_filters
    are unchanged.
    """
    entity = search_question.get("entity") or ""
    question = search_question.get("question") or ""
    response_type = search_question.get("response_type") or ""
    planner_filters = search_question.get("metadata_filters")
    if not isinstance(planner_filters, dict):
        planner_filters = {}

    collection, default_meta = resolve_entity_to_collection(entity, config_path)
    merged = {**default_meta, **planner_filters}

    return {
        "collection": collection,
        "question": question,
        "metadata_filters": merged,
        "response_type": response_type,
        "entity": entity,
    }


def get_known_entity_types(config_path: Optional[Path] = None) -> List[str]:
    """Return sorted list of entity types that map to collections (for prompt validation)."""
    mapping = get_entity_to_collection_mapping(config_path)
    return sorted(mapping.keys())


def resolve_search_questions_to_collections(
    search_questions: List[Dict[str, Any]],
    config_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Resolve a list of search_questions (from planner) to collection + merged metadata for each.
    Returns list of dicts with: collection, question, metadata_filters, response_type, entity.
    Items with unknown entity have collection=None; retrieval can skip or use graph service.
    """
    return [resolve_search_question_to_collection(sq, config_path) for sq in search_questions]
