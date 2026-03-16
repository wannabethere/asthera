"""
AttackControlMappingTool — orchestrate ATT&CK technique → control mapping pipeline.
Calls TacticContextualiserTool, FrameworkItemRetrievalTool, then LLM mapping + validation.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agents.tools.attack_tools import ATTACKEnrichmentTool
from app.core.settings import get_settings
from app.ingestion.attacktocve.prompts import (
    CONTROL_MAPPING_SYSTEM,
    CONTROL_MAPPING_USER,
    VALIDATION_SYSTEM,
    VALIDATION_USER,
    get_framework_preset,
)

logger = logging.getLogger(__name__)

def _get_tactic_context(technique_id: str, tactic: str) -> Dict[str, Any]:
    from app.agents.tools.tactic_contextualiser import _execute_tactic_contextualise
    return _execute_tactic_contextualise(technique_id, tactic)


def _get_framework_items(
    query: str,
    framework_id: str,
    tactic: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    from app.agents.tools.framework_item_retrieval import _execute_framework_item_retrieval
    return _execute_framework_item_retrieval(query, framework_id, tactic, top_k, 0.35)


def _get_framework_metadata(framework_id: str) -> tuple[str, str]:
    """Lookup framework_name and control_id_label from control_frameworks or prompts."""
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text

        with get_security_intel_session("cve_attack") as session:
            result = session.execute(
                text("SELECT framework_name, control_id_label FROM control_frameworks WHERE framework_id = :fid"),
                {"fid": framework_id},
            )
            row = result.fetchone()
            if row:
                return (row[0] or framework_id, row[1] or "item_id")
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.debug(f"control_frameworks lookup failed: {e}")
    preset = get_framework_preset(framework_id)
    return (
        preset.get("framework_name", framework_id),
        preset.get("control_id_label", "item_id"),
    )


class AttackControlMappingInput(BaseModel):
    """Input schema for AttackControlMappingTool."""
    technique_id: str = Field(description="ATT&CK technique ID (e.g., T1078)")
    tactic: str = Field(description="Kill chain phase slug (e.g., persistence)")
    framework_id: str = Field(description="Framework ID (e.g., nist_800_53r5, cis_v8_1)")
    top_k: int = Field(default=8, description="Number of candidate items to retrieve")
    cve_id: Optional[str] = Field(default=None, description="Optional CVE ID for CVE pipeline context")
    cve_context: Optional[Dict[str, Any]] = Field(default=None, description="Optional CVE detail for richer rationale")
    persist: bool = Field(default=True, description="Persist mappings to attack_control_mappings_multi")


class ControlMappingResult(BaseModel):
    """Single control mapping result."""
    technique_id: str
    tactic: str
    item_id: str
    framework_id: str
    relevance_score: float
    confidence: str
    rationale: str
    tactic_risk_lens: str
    blast_radius: str
    control_family: str
    attack_tactics: List[str]
    attack_platforms: List[str]
    loss_outcomes: List[str]


def _extract_json(text: str) -> Any:
    """Extract JSON from LLM response (handle markdown fences)."""
    text = text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
    return json.loads(text)


def _persist_control_mappings_multi(
    results: List[Dict[str, Any]],
    cve_id: Optional[str] = None,
    mapping_run_id: Optional[str] = None,
) -> int:
    """Persist mappings to attack_control_mappings_multi table."""
    if not results:
        return 0
    try:
        import uuid
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text

        run_id = mapping_run_id or str(uuid.uuid4())
        with get_security_intel_session("cve_attack") as session:
            for r in results:
                session.execute(
                    text("""
                        INSERT INTO attack_control_mappings_multi (
                            technique_id, tactic, item_id, framework_id,
                            relevance_score, confidence, rationale,
                            tactic_risk_lens, blast_radius,
                            attack_tactics, attack_platforms, loss_outcomes,
                            mapping_run_id, cve_id
                        ) VALUES (
                            :technique_id, :tactic, :item_id, :framework_id,
                            :relevance_score, :confidence, :rationale,
                            :tactic_risk_lens, :blast_radius,
                            :attack_tactics, :attack_platforms, :loss_outcomes,
                            :mapping_run_id, :cve_id
                        )
                        ON CONFLICT (technique_id, tactic, item_id, framework_id) DO UPDATE SET
                            relevance_score = EXCLUDED.relevance_score,
                            confidence = EXCLUDED.confidence,
                            rationale = EXCLUDED.rationale,
                            tactic_risk_lens = EXCLUDED.tactic_risk_lens,
                            blast_radius = EXCLUDED.blast_radius,
                            attack_tactics = EXCLUDED.attack_tactics,
                            attack_platforms = EXCLUDED.attack_platforms,
                            loss_outcomes = EXCLUDED.loss_outcomes,
                            mapping_run_id = EXCLUDED.mapping_run_id,
                            cve_id = EXCLUDED.cve_id,
                            updated_at = NOW()
                    """),
                    {
                        "technique_id": r["technique_id"],
                        "tactic": r["tactic"],
                        "item_id": r["item_id"],
                        "framework_id": r["framework_id"],
                        "relevance_score": r["relevance_score"],
                        "confidence": r["confidence"],
                        "rationale": r["rationale"],
                        "tactic_risk_lens": r.get("tactic_risk_lens", ""),
                        "blast_radius": r.get("blast_radius", "identity"),
                        "attack_tactics": r.get("attack_tactics", []),
                        "attack_platforms": r.get("attack_platforms", []),
                        "loss_outcomes": r.get("loss_outcomes", []),
                        "mapping_run_id": run_id,
                        "cve_id": cve_id,
                    },
                )
        return len(results)
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning(f"Failed to persist to attack_control_mappings_multi: {e}")
        return 0


def _execute_attack_control_map(
    technique_id: str,
    tactic: str,
    framework_id: str,
    top_k: int = 8,
    cve_id: Optional[str] = None,
    cve_context: Optional[Dict[str, Any]] = None,
    persist: bool = True,
) -> List[Dict[str, Any]]:
    """Execute AttackControlMappingTool."""
    from app.core.dependencies import get_llm

    tid = technique_id.strip().upper()
    tactic_slug = tactic.strip().lower().replace(" ", "-")

    # 1. Get technique
    settings = get_settings()
    pg_dsn = settings.get_attack_db_dsn() if hasattr(settings, "get_attack_db_dsn") else None
    enricher = ATTACKEnrichmentTool(use_postgres=bool(pg_dsn), pg_dsn=pg_dsn)
    technique = enricher.get_technique(tid)

    # 2. Get tactic context
    ctx = _get_tactic_context(tid, tactic_slug)
    tactic_risk_lens = ctx.get("tactic_risk_lens", "")
    blast_radius = ctx.get("blast_radius", "identity")

    # 3. Get framework items
    items = _get_framework_items(tactic_risk_lens, framework_id, tactic_slug, top_k)
    if not items:
        return []

    # 4. Framework metadata
    framework_name, control_id_label = _get_framework_metadata(framework_id)

    # 5. LLM mapping
    scenarios_json = json.dumps(items, indent=2)
    cve_section = ""
    if cve_id and cve_context:
        cve_section = f"\n=== CVE Context (for richer rationale) ===\nCVE: {cve_id}\n"
        if cve_context.get("description"):
            cve_section += f"Description: {cve_context['description'][:400]}...\n"
        if cve_context.get("affected_products"):
            cve_section += f"Affected: {', '.join(cve_context['affected_products'][:5])}\n"
        if cve_context.get("exploit_maturity"):
            cve_section += f"Exploit maturity: {cve_context['exploit_maturity']}\n"
        cve_section += "\n"
    user_prompt = CONTROL_MAPPING_USER.format(
        technique_id=tid,
        technique_name=technique.name,
        tactics=", ".join(technique.tactics),
        platforms=", ".join(technique.platforms),
        description=technique.description[:800],
        mitigations=json.dumps(technique.mitigations)[:300],
        data_sources=", ".join(technique.data_sources)[:200],
        framework_name=framework_name,
        top_k=len(items),
        scenarios_json=scenarios_json,
    )
    if cve_section:
        user_prompt = cve_section + user_prompt
    system_prompt = CONTROL_MAPPING_SYSTEM.format(
        framework_name=framework_name,
        control_id_label=control_id_label,
    )
    from langchain_core.messages import SystemMessage, HumanMessage
    llm = get_llm(temperature=0.2)
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    content = response.content if hasattr(response, "content") else str(response)
    try:
        mappings = _extract_json(content)
        if not isinstance(mappings, list):
            mappings = []
    except json.JSONDecodeError:
        logger.warning(f"LLM mapping returned invalid JSON: {content[:200]}")
        mappings = []

    # 6. LLM validation
    technique_summary = f"{tid} {technique.name}: {tactic_risk_lens[:200]}..."
    validation_user = VALIDATION_USER.format(
        framework_name=framework_name,
        technique_summary=technique_summary,
        raw_mappings_json=json.dumps(mappings, indent=2),
    )
    validation_system = VALIDATION_SYSTEM.format(framework_name=framework_name)
    val_response = llm.invoke([
        SystemMessage(content=validation_system),
        HumanMessage(content=validation_user),
    ])
    val_content = val_response.content if hasattr(val_response, "content") else str(val_response)
    try:
        val_data = _extract_json(val_content)
        corrected = val_data.get("corrected_mappings", mappings)
    except json.JSONDecodeError:
        corrected = mappings

    # 7. Build result list
    results = []
    for m in corrected:
        item_id = m.get("scenario_id") or m.get("item_id") or ""
        if not item_id:
            continue
        results.append({
            "technique_id": tid,
            "tactic": tactic_slug,
            "item_id": item_id,
            "framework_id": framework_id,
            "relevance_score": float(m.get("relevance_score", 0.5)),
            "confidence": m.get("confidence", "medium"),
            "rationale": m.get("rationale", ""),
            "tactic_risk_lens": tactic_risk_lens,
            "blast_radius": blast_radius,
            "control_family": m.get("control_family", ""),
            "attack_tactics": m.get("attack_tactics", technique.tactics),
            "attack_platforms": m.get("attack_platforms", technique.platforms),
            "loss_outcomes": m.get("loss_outcomes", []),
        })

    # 8. Persist to attack_control_mappings_multi when requested (CVE pipeline)
    if persist and results:
        _persist_control_mappings_multi(results, cve_id=cve_id)

    return results


def create_attack_control_mapping_tool() -> StructuredTool:
    """Create LangChain tool for ATT&CK → control mapping."""
    return StructuredTool.from_function(
        func=_execute_attack_control_map,
        name="attack_control_map",
        description="Map an ATT&CK technique (under a specific tactic) to framework controls. Returns relevance scores, confidence, rationale. Use kill_chain_phases slug for tactic.",
        args_schema=AttackControlMappingInput,
    )
