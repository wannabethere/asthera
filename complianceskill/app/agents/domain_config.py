"""
Domain Configuration — abstracts domain-specific constants for multi-domain pipelines.

Instead of hardcoding LMS focus areas, collection names, and keywords in Python,
each domain declares its configuration in ``config/domains/<domain_id>.json``.
The pipeline reads from ``DomainRegistry`` at runtime.

Usage::

    from app.agents.domain_config import DomainRegistry

    # In a node function:
    cfg = DomainRegistry.instance().get_for_state(state)
    focus_map = cfg.focus_area_category_map
    collection = cfg.collection("causal_edges")
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_DOMAINS_DIR = Path(__file__).resolve().parents[2] / "config" / "domains"
_DEFAULT_DOMAIN = "lms"


# ── Domain Config dataclass ──────────────────────────────────────────────────

@dataclass(frozen=True)
class DomainConfig:
    """
    Immutable domain configuration loaded from a JSON file.

    Holds all domain-specific constants that were previously hardcoded
    in Python modules (focus areas, collection names, keywords, etc.).
    """
    domain_id: str
    display_name: str
    description: str = ""
    state_key_prefix: str = "csod"
    mdl_collection_prefix: str = "csod_"
    default_use_case: str = "lms_learning_target"

    # Vector store collection names
    collections: Dict[str, str] = field(default_factory=dict)

    # Focus area → search keyword expansion
    focus_area_category_map: Dict[str, List[str]] = field(default_factory=dict)

    # Capability ID substring → provider source tokens
    capability_source_hints: Dict[str, List[str]] = field(default_factory=dict)

    # DT focus area → keyword hints (security-specific)
    dt_focus_hints: Dict[str, List[str]] = field(default_factory=dict)

    # Domain classification keywords
    domain_keywords: List[str] = field(default_factory=list)

    # Intent prefix patterns for domain classification
    intent_prefixes: List[str] = field(default_factory=list)

    # training_type → expanded search term (e.g., "mandatory" → "mandatory compliance")
    training_type_aliases: Dict[str, str] = field(default_factory=dict)

    # Available scoping dimensions for conversation layer
    scoping_dimensions: List[str] = field(default_factory=list)

    # Known data sources for this domain
    data_sources: List[str] = field(default_factory=list)

    # Personas applicable to this domain
    personas: List[str] = field(default_factory=list)

    # ── Accessors ─────────────────────────────────────────────────────────

    def collection(self, key: str) -> str:
        """Get a collection name by logical key (e.g., 'causal_edges')."""
        return self.collections.get(key, f"{self.mdl_collection_prefix}{key}")

    def expand_focus_areas(self, focus_areas: Sequence[str]) -> List[str]:
        """Expand focus area names to search keywords using the category map."""
        categories: List[str] = []
        for fa in focus_areas:
            for cat in self.focus_area_category_map.get(fa, [fa]):
                if cat not in categories:
                    categories.append(cat)
        return categories

    def expand_training_type(self, training_type: Optional[str]) -> Optional[str]:
        """Resolve training_type aliases (e.g., 'mandatory' → 'mandatory compliance')."""
        if not training_type or training_type == "all":
            return None
        return self.training_type_aliases.get(training_type, training_type)

    # ── Factory ───────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DomainConfig":
        return cls(
            domain_id=d["domain_id"],
            display_name=d["display_name"],
            description=d.get("description", ""),
            state_key_prefix=d.get("state_key_prefix", "csod"),
            mdl_collection_prefix=d.get("mdl_collection_prefix", "csod_"),
            default_use_case=d.get("default_use_case", "lms_learning_target"),
            collections=d.get("collections", {}),
            focus_area_category_map=d.get("focus_area_category_map", {}),
            capability_source_hints=d.get("capability_source_hints", {}),
            dt_focus_hints=d.get("dt_focus_hints", {}),
            domain_keywords=d.get("domain_keywords", []),
            intent_prefixes=d.get("intent_prefixes", []),
            training_type_aliases=d.get("training_type_aliases", {}),
            scoping_dimensions=d.get("scoping_dimensions", []),
            data_sources=d.get("data_sources", []),
            personas=d.get("personas", []),
        )

    @classmethod
    def from_json(cls, path: Path) -> "DomainConfig":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ── State Key Resolver ────────────────────────────────────────────────────────

class StateKeyResolver:
    """
    Resolves canonical state key names to domain-prefixed keys.

    Existing code continues using ``state["csod_intent"]`` directly.
    New code can use ``resolver.key("intent")`` → ``"csod_intent"``
    for domain-aware access without hardcoding the prefix.
    """

    def __init__(self, config: DomainConfig):
        self._prefix = config.state_key_prefix

    def key(self, canonical: str) -> str:
        """Resolve canonical name to prefixed state key."""
        return f"{self._prefix}_{canonical}"

    def get(self, state: Dict[str, Any], canonical: str, default: Any = None) -> Any:
        """Read a domain-prefixed key from state."""
        return state.get(self.key(canonical), default)

    def set(self, state: Dict[str, Any], canonical: str, value: Any) -> None:
        """Write a domain-prefixed key to state."""
        state[self.key(canonical)] = value


# ── Domain Registry (singleton) ──────────────────────────────────────────────

class DomainRegistry:
    """
    Singleton registry of domain configurations.

    Loads all ``config/domains/*.json`` on first access. Provides lookup by
    domain_id and state-based resolution (reads ``primary_domain`` or
    ``vertical`` from state, falls back to default).
    """

    _instance: Optional["DomainRegistry"] = None

    def __init__(self, domains_dir: Optional[Path] = None):
        self._domains: Dict[str, DomainConfig] = {}
        self._load(domains_dir or _DOMAINS_DIR)

    def _load(self, domains_dir: Path) -> None:
        if not domains_dir.is_dir():
            logger.warning("Domains config directory not found: %s", domains_dir)
            return
        for path in sorted(domains_dir.glob("*.json")):
            try:
                cfg = DomainConfig.from_json(path)
                self._domains[cfg.domain_id] = cfg
                logger.debug("Loaded domain config: %s from %s", cfg.domain_id, path.name)
            except Exception:
                logger.warning("Failed to load domain config: %s", path.name, exc_info=True)
        logger.info("Loaded %d domain configs from %s", len(self._domains), domains_dir)

    @classmethod
    def instance(cls, domains_dir: Optional[Path] = None) -> "DomainRegistry":
        if cls._instance is None:
            cls._instance = cls(domains_dir)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear singleton — useful for tests."""
        cls._instance = None

    # ── Lookup ────────────────────────────────────────────────────────────

    def get(self, domain_id: str) -> Optional[DomainConfig]:
        return self._domains.get(domain_id)

    def default(self) -> DomainConfig:
        """Return the default (LMS) domain config."""
        cfg = self._domains.get(_DEFAULT_DOMAIN)
        if cfg:
            return cfg
        # Emergency fallback — should never happen if lms.json exists
        return DomainConfig(domain_id="lms", display_name="LMS (fallback)")

    def all_domain_ids(self) -> List[str]:
        return list(self._domains.keys())

    def all_configs(self) -> Dict[str, DomainConfig]:
        return dict(self._domains)

    def get_for_state(self, state: Dict[str, Any]) -> DomainConfig:
        """
        Resolve domain config from pipeline state.

        Resolution order:
          1. ``state["primary_domain"]`` (set by lexy_domain_context)
          2. ``state["vertical"]`` (legacy key)
          3. ``state["domain_classification"]["primary"]`` (if present)
          4. Default (LMS)
        """
        # 1. primary_domain
        domain = state.get("primary_domain")
        if domain and domain in self._domains:
            return self._domains[domain]

        # 2. vertical (legacy)
        vertical = state.get("vertical")
        if vertical and vertical in self._domains:
            return self._domains[vertical]

        # 3. domain_classification
        dc = state.get("domain_classification")
        if isinstance(dc, dict):
            primary = dc.get("primary")
            if primary and primary in self._domains:
                return self._domains[primary]

        # 4. Default
        return self.default()

    def resolver_for_state(self, state: Dict[str, Any]) -> StateKeyResolver:
        """Get a StateKeyResolver for the domain detected in state."""
        return StateKeyResolver(self.get_for_state(state))

    # ── Domain keyword aggregation (for lexy_domain_context) ──────────────

    def all_domain_keywords(self) -> Dict[str, List[str]]:
        """Return {domain_id: keywords} for all loaded domains."""
        return {did: cfg.domain_keywords for did, cfg in self._domains.items()}

    def all_intent_prefixes(self) -> Dict[str, List[str]]:
        """Return {domain_id: intent_prefixes} for all loaded domains."""
        return {did: cfg.intent_prefixes for did, cfg in self._domains.items()}

    def all_capability_source_hints(self) -> Dict[str, List[str]]:
        """Merge all domain capability_source_hints into a single dict."""
        merged: Dict[str, List[str]] = {}
        for cfg in self._domains.values():
            for k, v in cfg.capability_source_hints.items():
                merged[k] = list(v)
        return merged

    def all_dt_focus_hints(self) -> Dict[str, List[str]]:
        """Merge all domain dt_focus_hints into a single dict."""
        merged: Dict[str, List[str]] = {}
        for cfg in self._domains.values():
            for k, v in cfg.dt_focus_hints.items():
                merged[k] = list(v)
        return merged
