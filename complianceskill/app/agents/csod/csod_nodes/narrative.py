"""User-facing narrative stream for CSOD conversational flows (SSE-friendly)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agents.csod.csod_nodes._helpers import CSOD_State


def append_csod_narrative(
    state: CSOD_State,
    phase: str,
    title: str,
    message: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Append one narrative line for UI/SSE (step_start / step_detail / step_end)."""
    if "csod_narrative_stream" not in state:
        state["csod_narrative_stream"] = []
    stream: List[Dict[str, Any]] = state["csod_narrative_stream"]
    stream.append({
        "ts": datetime.utcnow().isoformat() + "Z",
        "phase": phase,
        "title": title,
        "message": message,
        "meta": meta or {},
    })
