"""
Stage 5b: Final Detection Artifact Assembler — LLM-powered composition
of a coherent detection/triage deliverable from all sub-graph outputs.

Unlike simple dict packaging, this node uses an LLM to:
  - Compose a unified detection narrative connecting rules, metrics, and controls
  - Generate executive summary appropriate to the request type
  - Cross-reference SIEM rules ↔ metrics ↔ controls into a cohesive playbook
  - Fill gaps when DT ran without MDL (LLM generates recommendations directly)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.orchestrator.orchestrator_state import OrchestratorState

logger = logging.getLogger(__name__)


def final_detection_artifact_assembler_node(state: OrchestratorState) -> OrchestratorState:
    """
    LLM-powered assembly of final detection/triage artifacts.

    The LLM composes a coherent deliverable from merged sub-graph outputs,
    cross-referencing detection rules with metrics and controls. When MDL
    was unavailable, the LLM fills in generic recommendations.

    Reads: merged_results, request_classification, user_query, capabilities_needed
    Writes: final_artifacts
    """
    merged = state.get("merged_results", {})
    classification = state.get("request_classification", {})
    capabilities = state.get("capabilities_needed", {})
    request_type = classification.get("request_type", "analysis_only")
    user_query = state.get("user_query", "")

    # Collect raw materials from sub-graphs
    raw_materials = _collect_raw_materials(merged)

    # Use LLM to compose the final artifact
    try:
        assembled = _llm_assemble(user_query, request_type, capabilities, raw_materials, state)
    except Exception as e:
        logger.warning("LLM artifact assembly failed, using structured fallback: %s", e)
        assembled = _structured_fallback(request_type, raw_materials)

    # Merge LLM-composed artifact with raw data (LLM adds narrative/summary, raw keeps data integrity)
    final: Dict[str, Any] = {
        "request_type": request_type,
        "deliverables": [],

        # LLM-composed sections
        "executive_summary": assembled.get("executive_summary", ""),
        "detection_narrative": assembled.get("detection_narrative", ""),
        "triage_procedures": assembled.get("triage_procedures", ""),
        "implementation_roadmap": assembled.get("implementation_roadmap", ""),
        "gap_analysis": assembled.get("gap_analysis", ""),
    }

    # Raw data artifacts (preserved for programmatic consumption)
    if raw_materials.get("siem_rules"):
        final["siem_rules"] = raw_materials["siem_rules"]
        final["deliverables"].append("siem_rules")

    if raw_materials.get("playbook"):
        final["playbook"] = raw_materials["playbook"]
        final["deliverables"].append("playbook")

    if raw_materials.get("metric_recommendations"):
        final["metric_recommendations"] = raw_materials["metric_recommendations"]
        final["deliverables"].append("metric_recommendations")

    if raw_materials.get("kpi_recommendations"):
        final["kpi_recommendations"] = raw_materials["kpi_recommendations"]
        final["deliverables"].append("kpi_recommendations")

    if raw_materials.get("dashboard"):
        final["dashboard"] = raw_materials["dashboard"]
        final["deliverables"].append("dashboard")

    if raw_materials.get("medallion_plan"):
        final["medallion_plan"] = raw_materials["medallion_plan"]
        final["deliverables"].append("medallion_plan")

    if raw_materials.get("data_science_insights"):
        final["data_science_insights"] = raw_materials["data_science_insights"]
        final["deliverables"].append("data_science_insights")

    if raw_materials.get("selected_layout"):
        final["selected_layout"] = raw_materials["selected_layout"]

    # DT hand-off context
    if raw_materials.get("dt_data_analysis_context"):
        final["data_analysis_handoff"] = raw_materials["dt_data_analysis_context"]
        final["deliverables"].append("data_analysis_handoff")

    # LLM-composed deliverables
    if final.get("executive_summary"):
        final["deliverables"].append("executive_summary")
    if final.get("detection_narrative"):
        final["deliverables"].append("detection_narrative")
    if final.get("triage_procedures"):
        final["deliverables"].append("triage_procedures")
    if final.get("implementation_roadmap"):
        final["deliverables"].append("implementation_roadmap")

    final["summary"] = merged.get("summary", {})
    final["assembly_method"] = "llm"

    state["final_artifacts"] = final

    logger.info("LLM artifact assembly: %d deliverables: %s", len(final["deliverables"]), final["deliverables"])
    _log_step(state, "final_detection_artifact_assembler", {
        "deliverables": final["deliverables"],
        "assembly_method": "llm",
    })
    return state


# ── LLM assembly ──────────────────────────────────────────────────────────────

def _llm_assemble(
    user_query: str,
    request_type: str,
    capabilities: Dict[str, Any],
    raw_materials: Dict[str, Any],
    state: OrchestratorState,
) -> Dict[str, Any]:
    """Use LLM to compose a cohesive detection/triage deliverable."""
    llm = get_llm(temperature=0.2)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _ASSEMBLER_PROMPT),
        ("human", "{input}"),
    ])

    # Build condensed context for LLM (token-aware truncation)
    context_parts = [
        f"User request: {user_query}",
        f"Request type: {request_type}",
        f"MDL available: {capabilities.get('has_data_sources', False)}",
        f"Framework context: {capabilities.get('has_framework_context', False)}",
    ]

    # SIEM rules summary
    rules = raw_materials.get("siem_rules", [])
    if rules:
        rule_summaries = [
            {"name": r.get("name", r.get("rule_name", f"Rule {i}")), "severity": r.get("severity", "medium")}
            for i, r in enumerate(rules[:10])
        ]
        context_parts.append(f"\nSIEM rules ({len(rules)} total):\n{json.dumps(rule_summaries, indent=2)}")

    # Metrics summary
    metrics = raw_materials.get("metric_recommendations", [])
    if metrics:
        metric_names = [m.get("name", m.get("metric_id", "")) for m in metrics[:15]]
        context_parts.append(f"\nMetric recommendations ({len(metrics)} total): {', '.join(metric_names)}")

    # Controls & risks
    controls = raw_materials.get("controls", [])
    if controls:
        ctrl_codes = [c.get("control_code", c.get("id", "")) for c in controls[:10]]
        context_parts.append(f"\nMapped controls: {', '.join(ctrl_codes)}")

    risks = raw_materials.get("risks", [])
    if risks:
        risk_names = [r.get("risk_name", r.get("name", "")) for r in risks[:5]]
        context_parts.append(f"\nIdentified risks: {', '.join(risk_names)}")

    # Playbook template
    playbook = raw_materials.get("playbook")
    if playbook and isinstance(playbook, dict):
        context_parts.append(f"\nPlaybook template: {playbook.get('template', 'unknown')}")
        if playbook.get("executive_summary"):
            context_parts.append(f"DT executive summary: {str(playbook['executive_summary'])[:500]}")

    human_msg = "\n".join(context_parts)
    human_msg += "\n\nCompose the final detection/triage deliverable. Return JSON."

    chain = prompt | llm
    response = chain.invoke({"input": human_msg})
    content = response.content if hasattr(response, "content") else str(response)

    parsed = _parse_json(content)
    if parsed and isinstance(parsed, dict):
        return parsed

    # If LLM returned prose instead of JSON, wrap it
    return {
        "executive_summary": content[:2000] if content else "",
        "detection_narrative": "",
        "triage_procedures": "",
        "implementation_roadmap": "",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_raw_materials(merged: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all raw materials from merged results for LLM context."""
    return {
        "siem_rules": merged.get("siem_rules", []),
        "playbook": merged.get("playbook"),
        "playbook_template": merged.get("playbook_template"),
        "controls": merged.get("dt_controls", []),
        "risks": merged.get("dt_risks", []),
        "scenarios": merged.get("dt_scenarios", []),
        "metric_recommendations": merged.get("metric_recommendations", []),
        "kpi_recommendations": merged.get("kpi_recommendations", []),
        "dashboard": merged.get("dashboard"),
        "medallion_plan": merged.get("medallion_plan"),
        "data_science_insights": merged.get("data_science_insights", []),
        "selected_layout": merged.get("selected_layout"),
        "dt_data_analysis_context": merged.get("dt_data_analysis_context"),
    }


def _structured_fallback(request_type: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Non-LLM fallback: generate artifact sections from raw data."""
    rules = raw.get("siem_rules", [])
    metrics = raw.get("metric_recommendations", [])
    controls = raw.get("controls", [])

    summary_parts = []
    if rules:
        summary_parts.append(f"Generated {len(rules)} SIEM detection rules.")
    if metrics:
        summary_parts.append(f"Recommended {len(metrics)} monitoring metrics.")
    if controls:
        summary_parts.append(f"Mapped to {len(controls)} compliance controls.")
    if raw.get("playbook"):
        summary_parts.append("Assembled detection playbook with triage procedures.")

    return {
        "executive_summary": " ".join(summary_parts) if summary_parts else "Analysis complete.",
        "detection_narrative": "",
        "triage_procedures": "",
        "implementation_roadmap": "",
        "gap_analysis": "",
    }


def _parse_json(text: str) -> Any:
    import re
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _log_step(state: OrchestratorState, step_name: str, outputs: Dict) -> None:
    from datetime import datetime
    state.setdefault("execution_steps", [])
    state["execution_steps"].append({
        "step_name": step_name, "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(), "status": "completed",
        "outputs": outputs,
    })


_ASSEMBLER_PROMPT = """You are a security operations architect composing a final detection and triage deliverable.

Given the outputs from detection engineering (SIEM rules, playbooks) and data analysis (metrics, dashboards) sub-workflows, compose a cohesive deliverable.

Your output MUST be JSON with these sections:

```json
{
  "executive_summary": "2-3 paragraph markdown summary for leadership: what was analyzed, key findings, recommended actions",
  "detection_narrative": "Technical narrative connecting SIEM rules to the controls and risks they address. Explain the detection strategy.",
  "triage_procedures": "Step-by-step triage procedures for when each detection rule fires. Include severity classification and escalation paths.",
  "implementation_roadmap": "Prioritized implementation plan: which rules to deploy first, which metrics to instrument, what dashboards to build.",
  "gap_analysis": "Identified gaps: controls without detection coverage, metrics without data sources, areas needing further investigation."
}
```

Rules:
- Write in professional security operations language
- Cross-reference SIEM rules with their mapped controls
- If metrics are available, connect them to detection thresholds
- If MDL was unavailable, note that detection rules are based on generic patterns and recommend data source onboarding
- Keep each section focused and actionable — this is an operational document, not a report
- Use markdown formatting within each section"""
