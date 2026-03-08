"""
Utility to load prompts from markdown files. All prompts live under prompt_utils/.
"""
from pathlib import Path
from typing import Optional

# Centralized prompt directories under app/agents/prompt_utils/
_PROMPT_UTILS = Path(__file__).parent / "prompt_utils"
PROMPTS_BASE = _PROMPT_UTILS / "base"  # Default: nodes, calculation_planner, dt fallbacks
PROMPTS_MDL = _PROMPT_UTILS / "mdl"    # DT workflow (detection triage, etc.)
PROMPTS_DECISION_TREES = _PROMPT_UTILS / "decision_trees"
PROMPTS_CSOD = _PROMPT_UTILS / "csod"


def load_prompt(prompt_name: str, prompts_dir: Optional[str] = None) -> str:
    """
    Load a prompt from a markdown file.
    
    Args:
        prompt_name: Name of the prompt file (e.g., "01_intent_classifier" or "01_intent_classifier.md")
        prompts_dir: Optional path to prompts directory. If None, uses PROMPTS_BASE.
    
    Returns:
        The prompt content as a string.
    
    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    if prompts_dir is None:
        prompts_dir = PROMPTS_BASE
    else:
        prompts_dir = Path(prompts_dir)
    
    # Add .md extension if not present
    if not prompt_name.endswith(".md"):
        prompt_name = f"{prompt_name}.md"
    
    prompt_path = prompts_dir / prompt_name
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def get_prompt_path(prompt_name: str, prompts_dir: Optional[str] = None) -> Path:
    """
    Get the path to a prompt file without loading it.
    
    Args:
        prompt_name: Name of the prompt file
        prompts_dir: Optional path to prompts directory
    
    Returns:
        Path object to the prompt file
    """
    if prompts_dir is None:
        prompts_dir = PROMPTS_BASE
    else:
        prompts_dir = Path(prompts_dir)
    
    if not prompt_name.endswith(".md"):
        prompt_name = f"{prompt_name}.md"
    
    return prompts_dir / prompt_name
