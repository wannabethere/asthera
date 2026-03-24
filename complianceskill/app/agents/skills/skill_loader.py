"""
Skill Loader — discovers and loads AnalysisSkill definitions from disk.

Scans ``skills/definitions/*.json`` and builds an index keyed by skill_id.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from app.agents.skills.base_skill import AnalysisSkill

logger = logging.getLogger(__name__)

_DEFINITIONS_DIR = Path(__file__).resolve().parent / "definitions"


def load_all_skills(definitions_dir: Optional[Path] = None) -> Dict[str, AnalysisSkill]:
    """
    Load every ``*.json`` in *definitions_dir* and return ``{skill_id: AnalysisSkill}``.

    Gracefully skips files that fail to parse — logs a warning and continues.
    """
    root = definitions_dir or _DEFINITIONS_DIR
    skills: Dict[str, AnalysisSkill] = {}

    if not root.is_dir():
        logger.warning("Skill definitions directory not found: %s", root)
        return skills

    for path in sorted(root.glob("*.json")):
        try:
            skill = AnalysisSkill.from_json(path)
            skills[skill.skill_id] = skill
            logger.debug("Loaded skill: %s from %s", skill.skill_id, path.name)
        except Exception:
            logger.warning("Failed to load skill definition: %s", path.name, exc_info=True)

    logger.info("Loaded %d analysis skills from %s", len(skills), root)
    return skills


def load_skill(skill_id: str, definitions_dir: Optional[Path] = None) -> Optional[AnalysisSkill]:
    """Load a single skill by ID.  Returns None if the definition file doesn't exist."""
    root = definitions_dir or _DEFINITIONS_DIR
    path = root / f"{skill_id}.json"
    if not path.is_file():
        return None
    try:
        return AnalysisSkill.from_json(path)
    except Exception:
        logger.warning("Failed to load skill %s", skill_id, exc_info=True)
        return None
