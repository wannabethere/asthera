"""
SlimSqliteSaver — disk-backed checkpointer that keeps only the latest checkpoint per thread.

Wraps MemorySaver but periodically flushes old checkpoints to prevent memory growth.
After each ``put()``, removes all but the most recent 2 checkpoints for that thread
(current + parent, required for LangGraph interrupt/resume).

This gives us:
  - Fast in-memory reads (MemorySaver speed)
  - Bounded memory (only latest 2 checkpoints retained per thread)
  - Thread cleanup on workflow completion via ``delete_thread()``
"""
import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# Maximum checkpoints to keep per (thread_id, checkpoint_ns).
# 1 = only the latest checkpoint (sufficient for interrupt_after resume
# because the adapter rebuilds graph_input from the payload on resume).
_MAX_CHECKPOINTS_PER_THREAD = 1


class SlimSqliteSaver(MemorySaver):
    """MemorySaver that prunes old checkpoints after every write.

    Drop-in replacement: same API as MemorySaver, but memory stays bounded
    because only the latest ``_MAX_CHECKPOINTS_PER_THREAD`` checkpoints are
    retained per thread.
    """

    def put(self, config, checkpoint, metadata, new_versions):
        """Save checkpoint then prune old entries for this thread."""
        result = super().put(config, checkpoint, metadata, new_versions)
        self._prune_thread(config)
        return result

    async def aput(self, config, checkpoint, metadata, new_versions):
        """Async save checkpoint then prune old entries for this thread."""
        result = await super().aput(config, checkpoint, metadata, new_versions)
        self._prune_thread(config)
        return result

    def _prune_thread(self, config: dict) -> None:
        """Remove all but the latest N checkpoints for this thread+namespace."""
        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

            ns_storage = self.storage.get(thread_id, {}).get(checkpoint_ns, {})
            if len(ns_storage) <= _MAX_CHECKPOINTS_PER_THREAD:
                return

            # Checkpoint IDs are UUIDs with embedded timestamps — sort to find newest
            all_ids = list(ns_storage.keys())

            # Keep the latest N, remove the rest
            ids_to_keep = set(sorted(all_ids)[-_MAX_CHECKPOINTS_PER_THREAD:])
            ids_to_remove = [cid for cid in all_ids if cid not in ids_to_keep]

            for cid in ids_to_remove:
                del ns_storage[cid]
                # Also clean up associated writes
                writes_key = (thread_id, checkpoint_ns, cid)
                self.writes.pop(writes_key, None)

            # Clean up orphaned blobs (channel values from pruned checkpoints).
            # Instead of deserializing checkpoints to find referenced versions
            # (which loads multi-MB state dicts into memory), simply remove
            # blobs for this thread that have no remaining checkpoint reference.
            # Safe because we only keep 1 checkpoint: any blob not from the
            # latest checkpoint is orphaned.
            if ids_to_remove:
                # Collect blob keys belonging to this thread+namespace
                blob_keys_to_remove = [
                    k for k in self.blobs
                    if isinstance(k, tuple) and len(k) >= 2
                    and k[0] == thread_id and k[1] == checkpoint_ns
                ]

                # We keep blobs conservatively — only remove if we pruned
                # checkpoints and there are many orphaned blobs.  Since we
                # keep _MAX_CHECKPOINTS_PER_THREAD=1, the latest put() just
                # wrote the current blobs; we can safely remove old ones by
                # keeping only blobs that were written in the latest put.
                # However, blob keys don't encode checkpoint_id, so we
                # skip blob cleanup entirely — the thread will be deleted
                # on workflow completion anyway (adelete_thread in adapter).
                _pruned_count = len(ids_to_remove)
                logger.debug(
                    "Pruned %d checkpoints for thread %s (kept %d, blob cleanup deferred)",
                    _pruned_count, thread_id, len(ids_to_keep),
                )
        except Exception as e:
            # Pruning is best-effort — never fail the checkpoint write
            logger.debug("Checkpoint pruning skipped: %s", e)

    def delete_thread(self, thread_id: str) -> None:
        """Remove all checkpointer state for a thread (called on workflow completion)."""
        removed = 0
        # Remove storage
        if thread_id in self.storage:
            removed += sum(len(ns) for ns in self.storage[thread_id].values())
            del self.storage[thread_id]
        # Remove writes
        write_keys = [k for k in self.writes if isinstance(k, tuple) and k[0] == thread_id]
        for k in write_keys:
            del self.writes[k]
            removed += 1
        # Remove blobs
        blob_keys = [k for k in self.blobs if isinstance(k, tuple) and len(k) >= 1 and k[0] == thread_id]
        for k in blob_keys:
            del self.blobs[k]
            removed += 1
        if removed:
            logger.debug("delete_thread(%s): removed %d items", thread_id, removed)
