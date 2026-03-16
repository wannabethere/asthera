"""
FrameworkItemIngestTool — Populate FrameworkCollections.ITEMS for a given framework.
Reads from framework data (scenarios, controls, requirements, risks), runs LLM classifier
for tactic_domains and asset_types, upserts to framework_items Postgres and vector store.
"""

from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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


@dataclass
class FrameworkItemRecord:
    """Unified framework item for ingestion."""
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


def _get_attr(obj: Any, *keys: str, default: str = "") -> str:
    """Get attribute or dict key from obj."""
    for k in keys:
        if isinstance(obj, dict):
            v = obj.get(k)
        else:
            v = getattr(obj, k, None)
        if v:
            return str(v)
    return default


def _build_items_from_framework_data(
    framework_id: str,
    framework_data: Dict[str, Any],
) -> List[FrameworkItemRecord]:
    """
    Build unified framework items from loaded framework data.
    Prioritizes: scenarios > risks > controls > requirements.
    """
    items: List[FrameworkItemRecord] = []
    seen_ids: set = set()

    # Scenarios (CIS-style)
    for s in framework_data.get("scenarios", []):
        item_id = _get_attr(s, "scenario_id", "risk_id", default="")
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        items.append(FrameworkItemRecord(
            item_id=item_id,
            framework_id=framework_id,
            title=_get_attr(s, "name", default=""),
            control_family="",
            control_objective="",
            risk_description=_get_attr(s, "description", default=""),
            trigger=_get_attr(s, "trigger", default=""),
            loss_outcomes=getattr(s, "loss_outcomes", []) or (s.get("loss_outcomes", []) if isinstance(s, dict) else []),
            tactic_domains=[],
            asset_types=[],
            blast_radius="",
        ))

    # Risks (when different from scenarios)
    for r in framework_data.get("risks", []):
        item_id = _get_attr(r, "risk_id", "scenario_id", default="")
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        items.append(FrameworkItemRecord(
            item_id=str(item_id),
            framework_id=framework_id,
            title=_get_attr(r, "name", default=""),
            control_family="",
            control_objective="",
            risk_description=_get_attr(r, "description", default=""),
            trigger=_get_attr(r, "trigger", default=""),
            loss_outcomes=getattr(r, "loss_outcomes", []) or (r.get("loss_outcomes", []) if isinstance(r, dict) else []),
            tactic_domains=[],
            asset_types=[],
            blast_radius="",
        ))

    # Controls
    for c in framework_data.get("controls", []):
        item_id = _get_attr(c, "control_id", default="")
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        items.append(FrameworkItemRecord(
            item_id=item_id,
            framework_id=framework_id,
            title=_get_attr(c, "name", default=""),
            control_family=_get_attr(c, "domain", default=""),
            control_objective=_get_attr(c, "description", default=""),
            risk_description="",
            trigger="",
            loss_outcomes=[],
            tactic_domains=[],
            asset_types=[],
            blast_radius="",
        ))

    # Requirements
    for r in framework_data.get("requirements", []):
        item_id = _get_attr(r, "requirement_id", default="")
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        items.append(FrameworkItemRecord(
            item_id=item_id,
            framework_id=framework_id,
            title=item_id,
            control_family="",
            control_objective=_get_attr(r, "description", default=""),
            risk_description="",
            trigger="",
            loss_outcomes=[],
            tactic_domains=[],
            asset_types=[],
            blast_radius="",
        ))

    return items


def _classify_single_batch(batch: List[FrameworkItemRecord], llm, tactic_options: str, asset_options: str) -> None:
    """Classify a single batch of items via LLM. Mutates items in place."""
    import re
    texts = []
    for item in batch:
        text = f"{item.title}. {item.control_objective}. {item.risk_description}. {item.trigger}"
        texts.append(text[:1500])

    prompt = f"""Classify each control/risk item. For each, return tactic_domains (list of ATT&CK tactic slugs) and asset_types (list of asset types).
Tactic slugs (use only these): {tactic_options}
Asset types (use only these): {asset_options}

Items (one per line, numbered):
"""
    for j, t in enumerate(texts):
        prompt += f"\n{j+1}. {t[:500]}..."

    prompt += """

Return valid JSON array, one object per item: [{"tactic_domains": ["persistence", ...], "asset_types": ["identity", ...]}, ...]
Same order as items. Use empty lists if unclear."""

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        if "```" in content:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if m:
                content = m.group(1).strip()
        data = json.loads(content.strip())
        for j, item in enumerate(batch):
            if j < len(data):
                d = data[j]
                item.tactic_domains = d.get("tactic_domains", []) or []
                item.asset_types = d.get("asset_types", []) or []
                item.blast_radius = item.asset_types[0] if item.asset_types else "identity"
    except Exception as e:
        logger.warning(f"LLM classification failed for batch: {e}")


def _classify_item_batch(
    items: List[FrameworkItemRecord],
    llm,
    batch_size: int = 5,
    max_concurrent: int = 5,
) -> None:
    """
    Run LLM classifier to derive tactic_domains and asset_types for each item.
    Uses up to max_concurrent (default 5) parallel OpenAI calls for speed.
    """
    tactic_options = "initial-access, execution, persistence, privilege-escalation, defense-evasion, credential-access, discovery, lateral-movement, collection, command-and-control, exfiltration, impact"
    asset_options = "identity, endpoint, data, network, process, application, cloud"

    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(_classify_single_batch, batch, llm, tactic_options, asset_options): batch
            for batch in batches
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.warning(f"Batch classification error: {e}")


def _ensure_control_framework(framework_id: str) -> None:
    """Ensure framework exists in control_frameworks table."""
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text

        framework_name = framework_id.replace("_", " ").title()
        with get_security_intel_session("cve_attack") as session:
            session.execute(
                text("""
                    INSERT INTO control_frameworks (framework_id, framework_name, control_id_label, qdrant_collection, is_active)
                    VALUES (:fid, :name, 'item_id', 'framework_items', true)
                    ON CONFLICT (framework_id) DO NOTHING
                """),
                {"fid": framework_id, "name": framework_name},
            )
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning(f"Could not ensure control_framework: {e}")


def _upsert_framework_items_postgres(items: List[FrameworkItemRecord]) -> int:
    """Upsert items to framework_items Postgres table."""
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text

        count = 0
        with get_security_intel_session("cve_attack") as session:
            for item in items:
                session.execute(
                    text("""
                        INSERT INTO framework_items
                        (item_id, framework_id, title, control_family, control_objective,
                         risk_description, trigger, loss_outcomes, tactic_domains, asset_types, blast_radius)
                        VALUES (:item_id, :framework_id, :title, :control_family, :control_objective,
                                :risk_description, :trigger, :loss_outcomes, :tactic_domains, :asset_types, :blast_radius)
                        ON CONFLICT (item_id, framework_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            control_family = EXCLUDED.control_family,
                            control_objective = EXCLUDED.control_objective,
                            risk_description = EXCLUDED.risk_description,
                            trigger = EXCLUDED.trigger,
                            loss_outcomes = EXCLUDED.loss_outcomes,
                            tactic_domains = EXCLUDED.tactic_domains,
                            asset_types = EXCLUDED.asset_types,
                            blast_radius = EXCLUDED.blast_radius,
                            updated_at = NOW()
                    """),
                    {
                        "item_id": item.item_id,
                        "framework_id": item.framework_id,
                        "title": item.title,
                        "control_family": item.control_family or "",
                        "control_objective": item.control_objective or "",
                        "risk_description": item.risk_description or "",
                        "trigger": item.trigger or "",
                        "loss_outcomes": item.loss_outcomes or [],
                        "tactic_domains": item.tactic_domains or [],
                        "asset_types": item.asset_types or [],
                        "blast_radius": item.blast_radius or "identity",
                    },
                )
                count += 1
        return count
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning(f"Postgres framework_items upsert failed: {e}")
        return 0


async def _upsert_framework_items_vector_store(items: List[FrameworkItemRecord]) -> int:
    """Upsert items to FrameworkCollections.ITEMS vector store."""
    from app.storage.collections import FrameworkCollections
    from app.storage.vector_store import get_vector_store_client

    client = get_vector_store_client()
    try:
        await client.initialize()
    except Exception:
        pass

    documents = []
    metadatas = []
    ids = []

    for item in items:
        text = f"{item.title}. {item.control_objective}. {item.risk_description}. {item.trigger}"
        text = text.strip() or item.title
        doc_id = f"{item.framework_id}::{item.item_id}"
        documents.append(text[:4000])
        metadatas.append({
            "item_id": item.item_id,
            "framework_id": item.framework_id,
            "title": item.title,
            "control_family": item.control_family,
            "control_objective": item.control_objective or "",
            "risk_description": item.risk_description or "",
            "trigger": item.trigger or "",
            "loss_outcomes": item.loss_outcomes or [],
            "tactic_domains": item.tactic_domains or [],
            "asset_types": item.asset_types or [],
            "blast_radius": item.blast_radius or "identity",
        })
        ids.append(doc_id)

    if not documents:
        return 0

    # Delete existing items for this framework (one filter-based call instead of N per-id calls)
    framework_id = items[0].framework_id if items else ""
    if framework_id:
        try:
            await client.delete(
                collection_name=FrameworkCollections.ITEMS,
                where={"framework_id": framework_id},
            )
        except Exception as e:
            logger.debug(f"Pre-upsert delete by framework_id skipped: {e}")

    await client.add_documents(
        collection_name=FrameworkCollections.ITEMS,
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )
    return len(ids)


def ingest_framework_items(
    framework_id: str,
    use_llm_classifier: bool = True,
) -> Dict[str, Any]:
    """
    Ingest framework items for a single framework into Postgres and vector store.

    Args:
        framework_id: Framework identifier (e.g., cis_controls_v8_1)
        use_llm_classifier: Whether to run LLM to derive tactic_domains/asset_types

    Returns:
        Dict with items_loaded, items_postgres, items_vector_store, errors
    """
    from .framework_loaders import load_all_framework_data
    from app.core.dependencies import get_llm

    result = {"items_loaded": 0, "items_postgres": 0, "items_vector_store": 0, "errors": []}

    try:
        framework_data = load_all_framework_data(framework_id)
        items = _build_items_from_framework_data(framework_id, framework_data)
        result["items_loaded"] = len(items)

        if not items:
            logger.warning(f"No items to ingest for {framework_id}")
            return result

        if use_llm_classifier:
            llm = get_llm(temperature=0.1)
            _classify_item_batch(items, llm)

        _ensure_control_framework(framework_id)
        result["items_postgres"] = _upsert_framework_items_postgres(items)
        result["items_vector_store"] = _run_async(_upsert_framework_items_vector_store(items))

        logger.info(f"Framework items ingest {framework_id}: {result['items_vector_store']} to vector store, {result['items_postgres']} to Postgres")
    except Exception as e:
        logger.error(f"Framework items ingest failed for {framework_id}: {e}")
        result["errors"].append(str(e))

    return result


def ingest_all_framework_items(
    frameworks: Optional[List[str]] = None,
    skip_frameworks: Optional[List[str]] = None,
    use_llm_classifier: bool = True,
) -> Dict[str, Any]:
    """
    Ingest framework items for all frameworks in batch.

    Args:
        frameworks: Optional list of framework IDs (defaults to all)
        skip_frameworks: Optional list to skip
        use_llm_classifier: Whether to run LLM classifier

    Returns:
        Dict with total_frameworks, successful, failed, results per framework
    """
    from .framework_helper import list_frameworks

    if frameworks is None:
        frameworks = list_frameworks()
    if skip_frameworks:
        frameworks = [f for f in frameworks if f not in skip_frameworks]

    report = {
        "total_frameworks": len(frameworks),
        "successful": 0,
        "failed": 0,
        "results": [],
    }

    for fw in frameworks:
        r = ingest_framework_items(fw, use_llm_classifier=use_llm_classifier)
        report["results"].append({"framework": fw, **r})
        if r["errors"]:
            report["failed"] += 1
        else:
            report["successful"] += 1

    return report
