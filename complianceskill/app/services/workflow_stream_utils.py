"""
Shared utilities for workflow SSE streaming.

Provides constant updates via:
- LLM token streaming (on_chat_model_stream → llm_chunk)
- LLM start/end (on_chat_model_start/end → llm_start/llm_end)
- Progress/heartbeat events during long-running nodes
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, AsyncGenerator

logger = logging.getLogger(__name__)


def _extract_chunk_content(chunk: Any) -> Optional[str]:
    """Extract text content from LLM chunk (AIMessageChunk or similar)."""
    if chunk is None:
        return None
    if isinstance(chunk, str):
        return chunk if chunk else None
    if hasattr(chunk, "content"):
        c = chunk.content
        return str(c) if c else None
    return str(chunk) if chunk else None


def maybe_llm_stream_event(event: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
    """
    Convert LangChain/LangGraph LLM streaming events to SSE event dicts.

    Returns an SSE event dict to yield, or None if not an LLM streaming event.
    """
    event_kind = event.get("event")
    event_name = event.get("name", "")
    run_id = event.get("run_id", "")

    if event_kind == "on_chat_model_stream":
        data = event.get("data", {})
        chunk = data.get("chunk")
        content = _extract_chunk_content(chunk)
        if content:
            return {
                "event": "llm_chunk",
                "data": {
                    "session_id": session_id,
                    "content": content,
                    "node": event_name,
                    "run_id": run_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }

    elif event_kind == "on_chat_model_start":
        return {
            "event": "llm_start",
            "data": {
                "session_id": session_id,
                "model": event_name,
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    elif event_kind == "on_chat_model_end":
        return {
            "event": "llm_end",
            "data": {
                "session_id": session_id,
                "model": event_name,
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    return None


async def heartbeat_generator(
    session_id: str,
    interval_seconds: float = 5.0,
    stop_event: asyncio.Event = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Yield heartbeat events at regular intervals to keep SSE connection alive.

    Use with asyncio.create_task and pass a stop event to cancel.
    """
    stop = stop_event or asyncio.Event()
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            yield {
                "event": "heartbeat",
                "data": {
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }


def progress_event(
    session_id: str,
    node: str,
    message: str,
    progress_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a progress SSE event for long-running operations."""
    data = {
        "session_id": session_id,
        "node": node,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if progress_pct is not None:
        data["progress_pct"] = progress_pct
    return {"event": "progress", "data": data}
