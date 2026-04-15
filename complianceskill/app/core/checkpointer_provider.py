"""
Checkpointer Provider — abstract factory for LangGraph checkpoint backends.

Resolves the checkpointer type from settings and returns a shared singleton:
  - CHECKPOINTER_TYPE=memory  → MemorySaver (fast, leaks across threads)
  - CHECKPOINTER_TYPE=sqlite  → AsyncSqliteSaver (file-backed, constant RAM)
  - CHECKPOINTER_TYPE=postgres → AsyncPostgresSaver (production-grade)

Falls back to MemorySaver if the required package is not installed.

Usage:
  # At startup (async context — e.g. FastAPI startup_event):
  await init_checkpointer()

  # Anywhere after startup (sync, returns cached singleton):
  cp = get_checkpointer()
"""
import logging
import os
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from app.core.slim_sqlite_saver import BoundedMemoryCheckpointer

logger = logging.getLogger(__name__)

# The properly initialized checkpointer (set by init_checkpointer)
_checkpointer: Optional[BaseCheckpointSaver] = None
_initialized: bool = False
_sqlite_conn = None  # prevent GC


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Get the application-wide checkpointer singleton.

    If ``init_checkpointer()`` hasn't run yet (e.g. module-level imports
    call ``create_*_app()`` before FastAPI startup), returns a temporary
    MemorySaver.  ``init_checkpointer()`` will replace it on all
    subsequently compiled graphs.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    # Pre-init fallback — will be replaced when init_checkpointer runs
    logger.info("get_checkpointer() called before init — returning temporary BoundedMemoryCheckpointer")
    _checkpointer = BoundedMemoryCheckpointer()
    return _checkpointer


async def init_checkpointer() -> BaseCheckpointSaver:
    """
    Initialize the real checkpointer singleton (call from async startup).

    Always runs the full initialization, replacing any temporary
    MemorySaver that ``get_checkpointer()`` may have returned earlier.
    Graphs compiled AFTER this call will use the real checkpointer.
    """
    global _checkpointer, _initialized

    from app.core.settings import get_settings, CheckpointerType

    settings = get_settings()
    config = settings.get_checkpointer_config()
    cp_type = config["type"]

    real_cp: Optional[BaseCheckpointSaver] = None

    if cp_type == CheckpointerType.SQLITE:
        real_cp = await _create_sqlite_checkpointer(config)
    elif cp_type == CheckpointerType.POSTGRES:
        real_cp = await _create_postgres_checkpointer(config)

    if real_cp is None:
        if cp_type != CheckpointerType.MEMORY:
            logger.error(
                "CHECKPOINTER_TYPE='%s' requested but initialization failed — "
                "falling back to BoundedMemoryCheckpointer (IN-MEMORY). "
                "Sessions will be lost on restart! "
                "Fix: ensure the requested checkpointer backend is installed and configured.",
                cp_type.value,
            )
        real_cp = BoundedMemoryCheckpointer()
        logger.info("Checkpointer: BoundedMemoryCheckpointer (in-memory, TTL=30min, max_threads=200)")

    _checkpointer = real_cp
    _initialized = True
    return _checkpointer


def clear_checkpointer() -> None:
    """Reset the singleton (for testing or reconfiguration)."""
    global _checkpointer, _initialized, _sqlite_conn
    _checkpointer = None
    _initialized = False
    _sqlite_conn = None


# ---------------------------------------------------------------------------
# Backend constructors (async)
# ---------------------------------------------------------------------------

async def _create_sqlite_checkpointer(config: dict) -> Optional[BaseCheckpointSaver]:
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        import aiosqlite
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-sqlite or aiosqlite not installed. "
            "Run: pip install langgraph-checkpoint-sqlite aiosqlite"
        )
        return None

    db_path = config.get("path", "./data/checkpoints.db")
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)

    try:
        global _sqlite_conn
        _sqlite_conn = await aiosqlite.connect(db_path)
        saver = AsyncSqliteSaver(_sqlite_conn)
        await saver.setup()
        logger.info("Checkpointer: AsyncSqliteSaver (%s)", db_path)
        return saver
    except Exception as e:
        logger.error("Failed to create AsyncSqliteSaver: %s", e, exc_info=True)
        return None


async def _create_postgres_checkpointer(config: dict) -> Optional[BaseCheckpointSaver]:
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        import psycopg
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-postgres or psycopg not installed. "
            "Run: pip install langgraph-checkpoint-postgres psycopg"
        )
        return None

    conn_string = config.get("conn_string")
    if not conn_string:
        logger.error("CHECKPOINTER_POSTGRES_CONN_STRING is required")
        return None

    try:
        conn = await psycopg.AsyncConnection.connect(conn_string)
        saver = AsyncPostgresSaver(conn)
        await saver.setup()
        logger.info("Checkpointer: AsyncPostgresSaver")
        return saver
    except Exception as e:
        logger.error("Failed to create AsyncPostgresSaver: %s", e, exc_info=True)
        return None
