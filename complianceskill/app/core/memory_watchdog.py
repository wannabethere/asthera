"""
Memory Watchdog — lightweight background RSS monitor.

Periodically samples process RSS and takes action at thresholds:
  - Warning log at 2 GB
  - Forced gc.collect() at 3 GB
  - Critical log at 4 GB

Started by the FastAPI startup hook, cancelled on shutdown.
"""
import asyncio
import gc
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_RSS_WARNING_BYTES = 2 * 1024**3   # 2 GB
_RSS_GC_BYTES = 3 * 1024**3        # 3 GB — force GC
_RSS_CRITICAL_BYTES = 4 * 1024**3  # 4 GB
_CHECK_INTERVAL_SECONDS = 30

_watchdog_task: Optional[asyncio.Task] = None


def _get_rss_bytes() -> int:
    """Get current process RSS in bytes (macOS + Linux compatible)."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        if os.uname().sysname == "Darwin":
            return usage.ru_maxrss          # bytes on macOS
        return usage.ru_maxrss * 1024       # KB → bytes on Linux
    except Exception:
        return 0


async def _watchdog_loop() -> None:
    """Background loop that monitors RSS memory usage."""
    warned = False
    _last_gc_time = 0.0
    while True:
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
        rss = _get_rss_bytes()
        if rss <= 0:
            continue
        rss_gb = rss / (1024**3)

        if rss >= _RSS_CRITICAL_BYTES:
            logger.critical(
                "Memory watchdog: RSS %.2f GB exceeds critical threshold (4 GB). "
                "Consider restarting the service.",
                rss_gb,
            )
            warned = True
            # Force GC at critical — but not more than once per 60s
            import time
            now = time.monotonic()
            if now - _last_gc_time > 60:
                collected = gc.collect()
                _last_gc_time = now
                logger.warning(
                    "Memory watchdog: forced gc.collect() at %.2f GB — freed %d objects",
                    rss_gb, collected,
                )
        elif rss >= _RSS_GC_BYTES:
            import time
            now = time.monotonic()
            if now - _last_gc_time > 120:
                collected = gc.collect()
                _last_gc_time = now
                logger.info(
                    "Memory watchdog: gc.collect() at %.2f GB — freed %d objects",
                    rss_gb, collected,
                )
            warned = True
        elif rss >= _RSS_WARNING_BYTES:
            if not warned:
                logger.warning(
                    "Memory watchdog: RSS %.2f GB exceeds warning threshold (2 GB).",
                    rss_gb,
                )
                warned = True
        else:
            if warned:
                logger.info(
                    "Memory watchdog: RSS %.2f GB back below warning threshold.",
                    rss_gb,
                )
                warned = False


def start_memory_watchdog() -> None:
    """Start the memory watchdog as a background asyncio task."""
    global _watchdog_task
    if _watchdog_task is not None and not _watchdog_task.done():
        return
    _watchdog_task = asyncio.create_task(_watchdog_loop())
    logger.info(
        "Memory watchdog started (warn=%d GB, critical=%d GB, interval=%ds)",
        _RSS_WARNING_BYTES // (1024**3),
        _RSS_CRITICAL_BYTES // (1024**3),
        _CHECK_INTERVAL_SECONDS,
    )


def stop_memory_watchdog() -> None:
    """Cancel the memory watchdog task."""
    global _watchdog_task
    if _watchdog_task is not None:
        _watchdog_task.cancel()
        _watchdog_task = None
        logger.info("Memory watchdog stopped")
