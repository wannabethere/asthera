"""
Analysis Skills — skill-based experience layer for analysis types.

Each analysis type (gap_analysis, crown_jewel, anomaly_detection, …) is
treated as a skill that a data engineer has.  Skills are shared across
csod_workflow and dt_workflow — same definition, different data context.

Usage::

    from app.agents.skills import SkillRegistry

    registry = SkillRegistry.instance()
    skill = registry.get("gap_analysis")
    if skill:
        context_block = skill.build_skill_context_block()
        dt_config = skill.to_dt_intent_config()
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from app.agents.skills.base_skill import (
    AnalysisSkill,
    CCEConfig,
    DTConfig,
    DataPlan,
    IntentSignals,
    RecommenderInstructions,
    ValidatorRules,
)
from app.agents.skills.skill_loader import load_all_skills, load_skill
from app.agents.skills.prompt_renderer import render_skill_prompt

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Singleton registry of loaded analysis skills.

    Provides lookup by skill_id and bridges to legacy intent_config dicts
    so that the existing csod / dt workflows continue to work unchanged.
    """

    _instance: Optional["SkillRegistry"] = None

    def __init__(self, definitions_dir: Optional[Path] = None):
        self._skills: Dict[str, AnalysisSkill] = load_all_skills(definitions_dir)

    @classmethod
    def instance(cls, definitions_dir: Optional[Path] = None) -> "SkillRegistry":
        """Return (or create) the singleton registry."""
        if cls._instance is None:
            cls._instance = cls(definitions_dir)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear singleton — useful for tests."""
        cls._instance = None

    # ── Lookup ────────────────────────────────────────────────────────────

    def get(self, skill_id: str) -> Optional[AnalysisSkill]:
        return self._skills.get(skill_id)

    def has(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def all_skill_ids(self) -> List[str]:
        return list(self._skills.keys())

    def skills_for_workflow(self, workflow: str) -> Dict[str, AnalysisSkill]:
        """Return skills available to a given workflow ('csod' or 'dt')."""
        return {
            sid: s for sid, s in self._skills.items()
            if workflow in s.workflows
        }

    # ── Legacy bridge (backward compat with intent_config.py) ─────────────

    def export_dt_intent_config(self) -> Dict[str, Dict]:
        """
        Build a DT_INTENT_CONFIG-compatible dict from all loaded skills.

        Entries where the skill has no dt_config are omitted — the existing
        DT_INTENT_CONFIG in intent_config.py is used as the fallback.
        """
        out: Dict[str, Dict] = {}
        for sid, skill in self._skills.items():
            cfg = skill.to_dt_intent_config()
            if cfg:
                out[sid] = cfg
        return out

    def export_cce_intent_config(self) -> Dict[str, Dict]:
        """Build a CCE_INTENT_CONFIG-compatible dict from all loaded skills."""
        return {sid: skill.to_cce_intent_config() for sid, skill in self._skills.items()}

    def export_catalog_entries(self) -> Dict[str, Dict]:
        """Build an INTENT_CATALOG_ENTRIES-compatible dict from all loaded skills."""
        return {sid: skill.to_catalog_entry() for sid, skill in self._skills.items()}

    # ── Convenience for node functions ────────────────────────────────────

    def resolve_skill_for_intent(self, intent: str) -> Optional[AnalysisSkill]:
        """
        Given a classified pipeline intent, return the matching skill.

        Falls through to None when no skill definition exists — the workflow
        continues with the traditional (non-skill) path.
        """
        return self._skills.get(intent)

    def get_skill_context_block(self, intent: str) -> Optional[str]:
        """Return the markdown context block for prompt injection, or None."""
        skill = self.resolve_skill_for_intent(intent)
        if skill:
            return skill.build_skill_context_block()
        return None

    def get_skill_prompt(self, intent: str, phase: str) -> Optional[str]:
        """Load a phase-specific prompt for the given intent's skill."""
        skill = self.resolve_skill_for_intent(intent)
        if skill:
            return skill.get_prompt(phase)
        return None


__all__ = [
    "AnalysisSkill",
    "CCEConfig",
    "DTConfig",
    "DataPlan",
    "IntentSignals",
    "RecommenderInstructions",
    "SkillRegistry",
    "ValidatorRules",
    "load_all_skills",
    "load_skill",
    "render_skill_prompt",
]
