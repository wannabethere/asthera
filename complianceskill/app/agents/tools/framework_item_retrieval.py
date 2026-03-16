"""
FrameworkItemRetrievalTool — query FrameworkCollections.ITEMS for framework controls
pre-filtered by tactic domain, semantically ranked by tactic risk lens.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.storage.collections import FrameworkCollections
from app.storage.vector_store import get_vector_store_client

logger = logging.getLogger(__name__)


class FrameworkItemRetrievalInput(BaseModel):
    """Input schema for FrameworkItemRetrievalTool."""
    query: str = Field(description="Tactic risk lens string from TacticContextualiserTool")
    framework_id: str = Field(description="Framework ID (e.g., cis_v8_1, nist_800_53r5)")
    tactic: str = Field(description="Kill chain phase slug for pre-filter (e.g., persistence)")
    top_k: int = Field(default=8, description="Number of results to return")
    score_threshold: float = Field(default=0.35, description="Minimum similarity score")


class FrameworkItemResult(BaseModel):
    """Single framework item result."""
    item_id: str
    framework_id: str
    title: str
    control_family: str
    control_objective: str
    risk_description: str
    trigger: str
    loss_outcomes: List[str]
    tactic_domains: List[str]
    asset_types: List[str]
    blast_radius: str
    similarity_score: float


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _format_result(
    item_id: str,
    framework_id: str,
    meta: Dict[str, Any],
    content: str,
    score: float,
) -> Dict[str, Any]:
    """Format a single result into FrameworkItemResult shape."""
    return {
        "item_id": item_id,
        "framework_id": framework_id,
        "title": meta.get("title", ""),
        "control_family": meta.get("control_family", ""),
        "control_objective": meta.get("control_objective", ""),
        "risk_description": meta.get("risk_description", content),
        "trigger": meta.get("trigger", ""),
        "loss_outcomes": meta.get("loss_outcomes", []),
        "tactic_domains": meta.get("tactic_domains", []),
        "asset_types": meta.get("asset_types", []),
        "blast_radius": meta.get("blast_radius", ""),
        "similarity_score": score,
    }


def _execute_framework_item_retrieval(
    query: str,
    framework_id: str,
    tactic: str,
    top_k: int = 8,
    score_threshold: float = 0.35,
) -> List[Dict[str, Any]]:
    """Execute FrameworkItemRetrievalTool."""

    async def _query_items():
        client = get_vector_store_client()
        try:
            await client.initialize()
        except Exception:
            pass
        where = client.normalize_filter({
            "framework_id": framework_id,
            "tactic_domains__contains": tactic,
        })
        result = await client.query(
            collection_name=FrameworkCollections.ITEMS,
            query_texts=[query],
            n_results=top_k * 2,  # Fetch extra for threshold filtering
            where=where,
        )
        return result

    try:
        result = _run_async(_query_items())
    except Exception as e:
        logger.warning(f"Framework ITEMS query failed, falling back to RISKS+SCENARIOS: {e}")
        return _fallback_risks_scenarios(query, framework_id, tactic, top_k, score_threshold)

    if not result or not result.get("documents") or not result["documents"][0]:
        return _fallback_risks_scenarios(query, framework_id, tactic, top_k, score_threshold)

    ids_list = result.get("ids", [[]])[0]
    docs_list = result["documents"][0]
    metas_list = result.get("metadatas", [[]])[0]
    distances_list = result.get("distances", [[]])[0]

    results = []
    for i in range(min(len(ids_list), len(metas_list))):
        doc_id = ids_list[i] if i < len(ids_list) else ""
        content = docs_list[i] if i < len(docs_list) else ""
        meta = metas_list[i] if i < len(metas_list) else {}
        distance = distances_list[i] if i < len(distances_list) else 1.0
        score = 1.0 / (1.0 + distance) if distance else 0.0

        if score < score_threshold:
            continue
        results.append(_format_result(
            doc_id or meta.get("item_id", ""),
            framework_id,
            meta,
            content,
            score,
        ))

    return results[:top_k]


def _fallback_risks_scenarios(
    query: str,
    framework_id: str,
    tactic: str,
    top_k: int,
    score_threshold: float,
) -> List[Dict[str, Any]]:
    """Fallback: query RISKS and SCENARIOS separately when ITEMS is empty."""
    merged: Dict[str, Dict[str, Any]] = {}

    async def _query_collection(collection: str):
        client = get_vector_store_client()
        try:
            await client.initialize()
        except Exception:
            pass
        where = client.normalize_filter({"framework_id": framework_id})
        return await client.query(
            collection_name=collection,
            query_texts=[query],
            n_results=top_k,
            where=where,
        )

    for coll in [FrameworkCollections.RISKS, FrameworkCollections.SCENARIOS]:
        try:
            result = _run_async(_query_collection(coll))
            if result and result.get("metadatas"):
                ids_list = result.get("ids", [[]])[0]
                docs_list = result["documents"][0] if result.get("documents") else []
                metas_list = result["metadatas"][0]
                distances_list = result.get("distances", [[]])[0]
                for i in range(len(metas_list)):
                    meta = metas_list[i]
                    item_id = meta.get("item_id") or meta.get("scenario_id") or meta.get("risk_id") or ids_list[i] if i < len(ids_list) else ""
                    content = docs_list[i] if i < len(docs_list) else ""
                    distance = distances_list[i] if i < len(distances_list) else 1.0
                    score = 1.0 / (1.0 + distance) if distance else 0.0
                    if score >= score_threshold and item_id:
                        if item_id not in merged or merged[item_id]["similarity_score"] < score:
                            merged[item_id] = _format_result(item_id, framework_id, meta, content, score)
        except Exception as e:
            logger.warning(f"Fallback {coll} query failed: {e}")

    return sorted(merged.values(), key=lambda x: x["similarity_score"], reverse=True)[:top_k]


def create_framework_item_retrieval_tool() -> StructuredTool:
    """Create LangChain tool for framework item retrieval."""
    return StructuredTool.from_function(
        func=_execute_framework_item_retrieval,
        name="framework_item_retrieval",
        description="Retrieve framework controls/items pre-filtered by tactic domain, ranked by semantic similarity to a tactic risk lens. Use when mapping ATT&CK techniques to controls.",
        args_schema=FrameworkItemRetrievalInput,
    )
