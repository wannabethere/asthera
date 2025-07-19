""" Utility functions for applying personas to format final answers. """

from typing import Optional
from .personas_config import Persona, get_persona, list_personas


def get_persona_instructions(persona_name: str) -> Optional[str]:
    """
    Get the instructions for a specific persona.

    Args:
        persona_name: The name of the persona

    Returns:
        The persona instructions or None if persona not found
    """
    persona = get_persona(persona_name)
    if not persona:
        available_personas = ", ".join(list_personas())
        raise ValueError(f"Persona '{persona_name}' not found. Available personas: {available_personas}")
    return persona.instructions


def apply_persona_to_final_answer(state, persona_name: Optional[str] = None) -> dict:
    """
    Record the persona used in the final answer in the state.
    This function is kept for backward compatibility but now only records which persona was used rather than reformatting the answer.

    Args:
        state: The current state containing the final answer
        persona_name: The name of the persona used

    Returns:
        Updated state with persona information
    """
    if not persona_name or persona_name.lower() == "none":
        return state

    try:
        # Just record which persona was used
        state["persona_used"] = persona_name
    except Exception as e:
        # If there's an error, record it
        state["persona_error"] = str(e)
    return state