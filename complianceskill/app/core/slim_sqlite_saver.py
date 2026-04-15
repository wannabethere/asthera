"""
BoundedMemoryCheckpointer — in-memory LangGraph checkpointer with TTL, LRU eviction,
and field-level state slimming.

Keeps only the latest checkpoint per thread and automatically evicts:
  - Threads idle for longer than TTL_SECONDS (default 30 min)
  - Oldest threads when the total count exceeds MAX_THREADS (LRU eviction)

Additionally, large/transient state fields (LLM prompts/responses, retrieved
data blobs, generated artifacts, etc.) are stripped from checkpoint storage so
only the minimal keys needed for conversation resumption are persisted.

This replaces both MemorySaver (unbounded growth → 8 GB+) and the old
SlimSqliteSaver (pruned checkpoints but still accumulated threads forever).

Memory model
------------
Each thread stores exactly 1 slimmed checkpoint (the latest).  With field
slimming the active state per thread drops from ~2–5 MB to ~50–200 KB, so
200 threads ≈ 10–40 MB — well under any practical ceiling.

Usage
-----
  from app.core.slim_sqlite_saver import BoundedMemoryCheckpointer
  cp = BoundedMemoryCheckpointer()          # defaults
  cp = BoundedMemoryCheckpointer(ttl=1800, max_threads=300)

Backward compatibility
----------------------
``SlimSqliteSaver`` is aliased to ``BoundedMemoryCheckpointer`` so existing
imports continue to work without changes.
"""
import copy
import logging
import time
from collections import OrderedDict
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# ── Defaults ─────────────────────────────────────────────────────────────────
_DEFAULT_TTL_SECONDS = 30 * 60   # 30 minutes idle → evict
_DEFAULT_MAX_THREADS = 200        # maximum live threads at any time
_MAX_CHECKPOINTS_PER_THREAD = 1   # only latest checkpoint needed for resume

# ── Fields to strip from channel_values before checkpoint storage ─────────────
# These are large/transient values that are re-derived or re-fetched each run
# and don't need to survive across conversation turns.
_CHECKPOINT_EXCLUDE_KEYS: frozenset = frozenset({
    # ── LLM I/O (can be 10s–100s KB each) ────────────────────────────────────
    "messages",           # full LangChain message history; grows with every exchange
    "llm_response",       # raw LLM response text
    "llm_prompt",         # full prompt dict sent to LLM
    # ── Execution logs (100 KB–500 KB) ───────────────────────────────────────
    "execution_steps",    # complete per-step agent logs
    "execution_plan",     # multi-step PlanStep list
    "context_cache",      # per-step retrieved data cache
    "refinement_history", # regeneration / quality loop history
    "validation_results", # ValidationResult objects
    # ── Compliance artifact output (can be MBs) ──────────────────────────────
    "siem_rules",
    "playbooks",
    "test_scripts",
    "data_pipelines",
    "dashboards",
    "vulnerability_mappings",
    "gap_analysis_results",
    "cross_framework_mappings",
    "metrics_context",
    "xsoar_indicators",
    "controls",
    "risks",
    "scenarios",
    "test_cases",
    "resolved_metrics",
    "resolved_focus_areas",
    "calculation_plan",
    # ── Detection & Triage (DT) pipeline blobs ───────────────────────────────
    "dt_retrieved_controls",
    "dt_retrieved_risks",
    "dt_retrieved_scenarios",
    "dt_resolved_schemas",
    "dt_mdl_retrieved_table_descriptions",
    "dt_mdl_l1_focus_scope",
    "dt_mdl_l2_capability_tables",
    "dt_mdl_l3_retrieval_queries",
    "dt_mdl_relation_edges",
    "dt_gold_standard_tables",
    "dt_scored_context",
    "dt_dropped_items",
    "dt_schema_gaps",
    "dt_rule_gaps",
    "dt_metric_recommendations",
    "dt_unmeasured_controls",
    "dt_assembled_playbook",
    "dt_reasoning_trace",
    "dt_generated_gold_model_sql",
    "dt_data_science_insights",
    "dt_demo_sql_result_sets",
    "dt_demo_sql_agent_context",
    # ── Planner output blobs ──────────────────────────────────────────────────
    "planner_siem_rules",
    "planner_metric_recommendations",
    "planner_execution_plan",
    "planner_medallion_plan",
    "goal_metric_definitions",
    "goal_metrics",
    "goal_output_intents",
    # ── CubeJS generation output ──────────────────────────────────────────────
    "cubejs_schema_files",
    "cubejs_generation_errors",
    # ── CSOD large/transient fields ───────────────────────────────────────────
    "csod_analysis_plan",             # schema-grounded analysis plan
    "csod_resolved_schemas_pruned",   # pruned schema columns list
    "csod_augmented_metrics",         # metric augmentation output
    "csod_augmented_metric_candidates",
    "csod_demo_sql_result_sets",
    "csod_demo_sql_agent_context",
    "csod_reasoning_narrative",       # full reasoning timeline (re-built each run)
    "csod_node_output",               # current-node transient output
    "csod_completion_narration",      # regenerated from recommendations
    "shared_per_metric_demo_artifacts",
    "shared_per_metric_artifact_stubs",
})


class BoundedMemoryCheckpointer(MemorySaver):
    """
    MemorySaver with TTL-based thread eviction and an LRU thread cap.

    After every write:
      1. The written thread's last-access timestamp is updated.
      2. Threads idle beyond ``ttl`` seconds are evicted.
      3. If the total thread count still exceeds ``max_threads``, the
         least-recently-used threads are evicted until within the limit.
      4. Old checkpoints within the current thread are pruned so only
         the latest ``_MAX_CHECKPOINTS_PER_THREAD`` remain.
    """

    def __init__(self, ttl: int = _DEFAULT_TTL_SECONDS, max_threads: int = _DEFAULT_MAX_THREADS):
        super().__init__()
        self._ttl = ttl
        self._max_threads = max_threads
        # OrderedDict preserves insertion order; we move-to-end on access
        # so the front is always the least-recently-used thread.
        self._last_access: OrderedDict[str, float] = OrderedDict()

    # ── Public write hooks ────────────────────────────────────────────────────

    def put(self, config, checkpoint, metadata, new_versions):
        result = super().put(config, self._slim_checkpoint(checkpoint), metadata, new_versions)
        self._after_write(config)
        return result

    async def aput(self, config, checkpoint, metadata, new_versions):
        result = await super().aput(config, self._slim_checkpoint(checkpoint), metadata, new_versions)
        self._after_write(config)
        return result

    # ── State slimming ────────────────────────────────────────────────────────

    @staticmethod
    def _slim_checkpoint(checkpoint: dict) -> dict:
        """Return a shallow-copied checkpoint with large/transient fields removed
        from ``channel_values`` so only resume-critical state is persisted."""
        channel_values = checkpoint.get("channel_values")
        if not isinstance(channel_values, dict):
            return checkpoint
        excluded = _CHECKPOINT_EXCLUDE_KEYS.intersection(channel_values)
        if not excluded:
            return checkpoint
        slimmed = dict(checkpoint)
        slimmed["channel_values"] = {k: v for k, v in channel_values.items() if k not in excluded}
        logger.debug(
            "BoundedMemoryCheckpointer: slimmed checkpoint — stripped %d key(s): %s",
            len(excluded), sorted(excluded),
        )
        return slimmed

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _after_write(self, config: dict) -> None:
        """Called after every checkpoint write; prunes + evicts as needed."""
        try:
            thread_id = config["configurable"]["thread_id"]
            self._touch(thread_id)
            self._prune_thread(config, thread_id)
            self._evict_expired()
            self._evict_lru()
        except Exception as exc:
            logger.debug("BoundedMemoryCheckpointer._after_write skipped: %s", exc)

    def _touch(self, thread_id: str) -> None:
        """Update last-access time for *thread_id* (move to end = most recent)."""
        self._last_access.pop(thread_id, None)
        self._last_access[thread_id] = time.monotonic()

    def _prune_thread(self, config: dict, thread_id: str) -> None:
        """Keep only the latest _MAX_CHECKPOINTS_PER_THREAD checkpoints for this thread."""
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        ns_storage = self.storage.get(thread_id, {}).get(checkpoint_ns, {})
        if len(ns_storage) <= _MAX_CHECKPOINTS_PER_THREAD:
            return
        all_ids = list(ns_storage.keys())
        keep = set(sorted(all_ids)[-_MAX_CHECKPOINTS_PER_THREAD:])
        for cid in [c for c in all_ids if c not in keep]:
            del ns_storage[cid]
            self.writes.pop((thread_id, checkpoint_ns, cid), None)

    def _evict_expired(self) -> None:
        """Remove all threads that have been idle longer than TTL."""
        now = time.monotonic()
        cutoff = now - self._ttl
        expired = [tid for tid, ts in self._last_access.items() if ts < cutoff]
        for tid in expired:
            self._delete_thread(tid)
        if expired:
            logger.info(
                "BoundedMemoryCheckpointer: evicted %d expired thread(s) (ttl=%ds)",
                len(expired), self._ttl,
            )

    def _evict_lru(self) -> None:
        """Evict least-recently-used threads until within max_threads limit."""
        evicted = 0
        while len(self._last_access) > self._max_threads:
            # OrderedDict front = LRU
            oldest_tid, _ = next(iter(self._last_access.items()))
            self._delete_thread(oldest_tid)
            evicted += 1
        if evicted:
            logger.info(
                "BoundedMemoryCheckpointer: evicted %d LRU thread(s) (max_threads=%d)",
                evicted, self._max_threads,
            )

    def _delete_thread(self, thread_id: str) -> None:
        """Remove all checkpointer state for *thread_id* and its access record."""
        self._last_access.pop(thread_id, None)
        if thread_id in self.storage:
            del self.storage[thread_id]
        write_keys = [k for k in self.writes if isinstance(k, tuple) and k[0] == thread_id]
        for k in write_keys:
            del self.writes[k]
        blob_keys = [k for k in self.blobs if isinstance(k, tuple) and len(k) >= 1 and k[0] == thread_id]
        for k in blob_keys:
            del self.blobs[k]

    # ── Public helper (called by adapter on workflow completion) ──────────────

    def delete_thread(self, thread_id: str) -> None:
        """Eagerly remove a completed thread (reduces memory immediately)."""
        self._delete_thread(thread_id)
        logger.debug("BoundedMemoryCheckpointer.delete_thread(%s)", thread_id)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return current memory stats for logging/monitoring."""
        return {
            "live_threads": len(self._last_access),
            "storage_threads": len(self.storage),
            "write_entries": len(self.writes),
            "blob_entries": len(self.blobs),
            "ttl_seconds": self._ttl,
            "max_threads": self._max_threads,
        }


# Backward-compat alias — existing imports of SlimSqliteSaver keep working
SlimSqliteSaver = BoundedMemoryCheckpointer
