"""Resolve the natural-language question from CSOD / planner state (checkpoint-safe)."""
from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import BaseMessage, HumanMessage


def effective_user_query(state: Dict[str, Any]) -> str:
    """
    Prefer ``user_query``; on checkpoint turns the payload often omits ``input`` and leaves
    ``user_query`` empty while the question still lives on ``messages``.
    """
    uq = (state.get("user_query") or "").strip()
    if uq:
        return uq
    messages = state.get("messages") or []
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            c = m.content
            if isinstance(c, str) and c.strip():
                return c.strip()
        if isinstance(m, BaseMessage) and m.type == "human":
            c = getattr(m, "content", "") or ""
            if isinstance(c, str) and c.strip():
                return c.strip()
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, str) and c.strip():
                return c.strip()
    return ""
