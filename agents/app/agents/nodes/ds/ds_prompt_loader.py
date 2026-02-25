"""Load DS RAG prompts from markdown files.

Prompts are in prompts/ subdirectory:
- prompts/ds_pipeline_planner.md
- prompts/ds_nl_question_generator.md
- prompts/ds_transformation_ambiguity_detector.md
- prompts/ds_transformation_resolution_builder.md

Design docs (ds_rag_planner_nl_prompts.md, ds_rag_transformation_prompts.md)
reference these prompt files.
"""
from pathlib import Path
from typing import Dict

_DS_DIR = Path(__file__).resolve().parent
_PROMPTS_DIR = _DS_DIR / "prompts"

_PROMPT_FILES = {
    "DS_PIPELINE_PLANNER": "ds_pipeline_planner.md",
    "DS_NL_QUESTION_GENERATOR": "ds_nl_question_generator.md",
    "DS_TRANSFORMATION_AMBIGUITY_DETECTOR": "ds_transformation_ambiguity_detector.md",
    "DS_TRANSFORMATION_RESOLUTION_BUILDER": "ds_transformation_resolution_builder.md",
}

_CACHE: Dict[str, str] = {}


def get_prompt(name: str) -> str:
    """Get a prompt by name. Loads from prompt md files and caches."""
    if name in _CACHE:
        return _CACHE[name]
    filename = _PROMPT_FILES.get(name)
    if not filename:
        return ""
    path = _PROMPTS_DIR / filename
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8").strip()
        _CACHE[name] = content
        return content
    except Exception:
        return ""


def get_all_prompts() -> Dict[str, str]:
    """Load and return all DS prompts from prompt md files."""
    for name in _PROMPT_FILES:
        if name not in _CACHE:
            get_prompt(name)
    return _CACHE.copy()
