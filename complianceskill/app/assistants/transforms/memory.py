"""
Conversational state and memory for the Transforms assistant.

Uses LangGraph checkpointing: thread_id in config identifies the conversation.
Checkpointer (MemorySaver by default; Postgres/vector store for optimization)
persists state so you can:
- Resume with the same thread_id
- get_state(config) / get_state_history(config) for start and back
- update_state(config, ...) to rewind or patch state

Pass a custom checkpointer (e.g. PostgresSaver) to build_transforms_graph(checkpointer=...)
to back memory with Postgres or another store.
"""
from typing import Any, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver


def get_transforms_config(
    thread_id: str,
    *,
    checkpoint_ns: Optional[str] = None,
    checkpoint_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build LangGraph config for conversational memory (save / start and back).

    Use the same thread_id across invokes to continue the same conversation.
    Use get_state(config) / get_state_history(config) on the compiled graph
    to read current or past checkpoints (start and back).

    Args:
        thread_id: Conversation/session id (required for checkpointer).
        checkpoint_ns: Optional namespace for sub-threads.
        checkpoint_id: Optional specific checkpoint to resume from (go back).

    Returns:
        Config dict for graph.invoke(..., config=...) and graph.get_state(config).
    """
    config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if checkpoint_ns is not None:
        config["configurable"]["checkpoint_ns"] = checkpoint_ns
    if checkpoint_id is not None:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    return config


def create_default_checkpointer() -> MemorySaver:
    """In-memory checkpointer for development. Replace with Postgres/vector store for production."""
    return MemorySaver()


def get_checkpointer(checkpointer: Optional[Any] = None) -> Any:
    """
    Resolve checkpointer: use provided one or default in-memory.

    For optimization, pass a checkpointer backed by Postgres or your vector store
    (any implementation of LangGraph's checkpointer protocol).
    """
    if checkpointer is not None:
        return checkpointer
    return create_default_checkpointer()
