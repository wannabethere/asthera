"""
CCE Sub-Graph Integration
==========================
Wires the ATT&CK → CIS Control mapper as a named node inside
the Causal Compliance Engine (CCE) LangGraph workflow.

Architecture position
---------------------
  [alert_triage_node]
       │
  [attack_control_mapper_node]   ← this module
       │
  [shapley_attribution_node]
       │
  [noisy_or_triage_node]

The mapper node:
  1. Reads technique_ids from the outer CCE state (produced by alert triage).
  2. Runs each technique through the compiled mapper sub-graph.
  3. Merges all ControlMapping results back into the CCE state.
  4. Enriches causal graph nodes with control coverage metadata.

CCE State extension
-------------------
Add these fields to your existing CCEState TypedDict:

    attack_control_mappings : List[ControlMapping]
    control_coverage_by_technique : Dict[str, List[str]]   # T-id → [scenario_ids]
    unmapped_techniques : List[str]
    control_enrichment_summary : str

Usage
-----
    from cce_integration import build_cce_attack_mapper_node, CCEStateExtension

    # In your CCE graph builder:
    workflow.add_node(
        "attack_control_mapper",
        build_cce_attack_mapper_node(vs_config, yaml_path),
    )
    workflow.add_edge("alert_triage", "attack_control_mapper")
    workflow.add_edge("attack_control_mapper", "shapley_attribution")
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from tools.control_loader import CISControlRegistry, load_cis_scenarios
from tools.vectorstore_retrieval import VectorStoreConfig
from tools.reverse_mapper import ScenarioToTechniqueMapper
from graph import build_graph, run_mapping, run_batch_mapping
from state import ControlMapping

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CCE State extension (merge these into your CCEState TypedDict)
# ---------------------------------------------------------------------------

class CCEStateExtension(TypedDict, total=False):
    """
    Fields this module adds to the CCE graph state.
    Merge into your existing CCEState with:

        class CCEState(ExistingCCEState, CCEStateExtension):
            pass
    """
    # Inputs (should already be in CCEState from alert_triage)
    technique_ids: List[str]                       # e.g. ["T1078", "T1059.001"]

    # Outputs (populated by attack_control_mapper node)
    attack_control_mappings: List[ControlMapping]
    control_coverage_by_technique: Dict[str, List[str]]  # T-id → [scenario_ids]
    unmapped_techniques: List[str]
    control_enrichment_summary: str
    control_enrichment_error: Optional[str]


# ---------------------------------------------------------------------------
# Node factory
# ---------------------------------------------------------------------------

def build_cce_attack_mapper_node(
    vs_config: VectorStoreConfig,
    yaml_path: str = "cis_controls_v8_1_risk_controls.yaml",
    min_confidence: str = "low",    # "high" | "medium" | "low"
    max_techniques: int = 10,       # cap to avoid runaway LLM calls
):
    """
    Returns a LangGraph node function that maps ATT&CK techniques → CIS controls.

    Args:
        vs_config       : Vector store config (Qdrant or Chroma).
        yaml_path       : Path to the CIS Controls YAML.
        min_confidence  : Filter mappings below this confidence level.
        max_techniques  : Maximum techniques to process per invocation.

    Returns:
        A node function compatible with `workflow.add_node(name, fn)`.
    """
    # Build shared sub-graph (compiled once, reused on every invocation)
    mapper_graph = build_graph(vs_config, yaml_path=yaml_path)
    registry = CISControlRegistry(load_cis_scenarios(yaml_path))

    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    min_rank = confidence_rank.get(min_confidence, 1)

    def _node(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        CCE node: reads technique_ids from state, runs mapper sub-graph,
        returns enriched state fields.
        """
        technique_ids: List[str] = state.get("technique_ids", [])

        if not technique_ids:
            logger.warning("[cce_mapper_node] No technique_ids in state – skipping")
            return {
                "attack_control_mappings": [],
                "control_coverage_by_technique": {},
                "unmapped_techniques": [],
                "control_enrichment_summary": "No techniques to map.",
                "control_enrichment_error": None,
            }

        # Cap
        techniques_to_process = technique_ids[:max_techniques]
        if len(technique_ids) > max_techniques:
            logger.warning(
                f"[cce_mapper_node] Capping at {max_techniques} techniques "
                f"(skipping {len(technique_ids) - max_techniques})"
            )

        logger.info(f"[cce_mapper_node] Mapping {len(techniques_to_process)} technique(s)")

        try:
            batch_results = run_batch_mapping(mapper_graph, techniques_to_process)
        except Exception as exc:
            logger.error(f"[cce_mapper_node] Batch mapping failed: {exc}")
            return {
                "attack_control_mappings": [],
                "control_coverage_by_technique": {},
                "unmapped_techniques": techniques_to_process,
                "control_enrichment_summary": f"Mapping failed: {exc}",
                "control_enrichment_error": str(exc),
            }

        # Collect and filter
        all_mappings: List[ControlMapping] = []
        coverage: Dict[str, List[str]] = {}
        unmapped: List[str] = []

        for tid, result_state in batch_results.items():
            if "error" in result_state and result_state["error"]:
                unmapped.append(tid)
                continue

            final = result_state.get("final_mappings", [])
            filtered = [
                m for m in final
                if confidence_rank.get(m.confidence, 1) >= min_rank
            ]

            if not filtered:
                unmapped.append(tid)
            else:
                all_mappings.extend(filtered)
                coverage[tid] = [m.scenario_id for m in filtered]

                # Update registry
                for m in filtered:
                    registry.update_controls(m.scenario_id, [tid])

        summary = _build_summary(all_mappings, unmapped, techniques_to_process)

        return {
            "attack_control_mappings": all_mappings,
            "control_coverage_by_technique": coverage,
            "unmapped_techniques": unmapped,
            "control_enrichment_summary": summary,
            "control_enrichment_error": None,
        }

    return _node


# ---------------------------------------------------------------------------
# Helper: causal graph enrichment
# ---------------------------------------------------------------------------

def enrich_causal_graph_nodes(
    causal_graph: Any,            # your NetworkX DiGraph or causal graph object
    mappings: List[ControlMapping],
    technique_attr: str = "technique_id",
    control_attr: str = "mapped_cis_controls",
) -> Any:
    """
    Attach CIS control scenario IDs to causal graph nodes that carry ATT&CK
    technique metadata.

    Assumes your causal graph nodes have a `technique_id` attribute.
    Adds a `mapped_cis_controls` attribute listing matched CIS scenario IDs.

    Example:
        G = enrich_causal_graph_nodes(G, state["attack_control_mappings"])
        for node, data in G.nodes(data=True):
            print(node, data.get("mapped_cis_controls", []))
    """
    try:
        import networkx as nx
    except ImportError:
        logger.error("networkx not installed; cannot enrich causal graph")
        return causal_graph

    # Build lookup: technique_id → [scenario_id]
    tech_to_scenarios: Dict[str, List[str]] = {}
    for m in mappings:
        tech_to_scenarios.setdefault(m.technique_id, []).append(m.scenario_id)

    enriched_count = 0
    for node in causal_graph.nodes:
        node_data = causal_graph.nodes[node]
        tid = node_data.get(technique_attr)
        if tid and tid in tech_to_scenarios:
            causal_graph.nodes[node][control_attr] = tech_to_scenarios[tid]
            enriched_count += 1

    logger.info(f"[causal_graph_enrich] Enriched {enriched_count} nodes with CIS control mappings")
    return causal_graph


# ---------------------------------------------------------------------------
# Helper: detection coverage gap analysis
# ---------------------------------------------------------------------------

def find_coverage_gaps(
    alert_techniques: List[str],
    mappings: List[ControlMapping],
    all_scenarios: List[Any],     # List[CISRiskScenario]
) -> Dict[str, Any]:
    """
    Identify CIS risk scenarios that are triggered by active alert techniques
    but have NO confirmed control mapping — these are the highest-priority gaps.

    Returns:
        {
          "covered_scenarios"    : [...],
          "uncovered_scenarios"  : [...],
          "gap_count"            : int,
          "gap_pct"              : float,
          "priority_gaps"        : [scenarios sorted by loss_outcome severity]
        }
    """
    covered_ids = {m.scenario_id for m in mappings}
    all_ids = {s.scenario_id for s in all_scenarios}
    uncovered = all_ids - covered_ids

    loss_severity = {"breach": 3, "compliance violation": 2, "operational impact": 1}

    def _severity(scenario) -> int:
        return max(
            (loss_severity.get(lo.strip(), 0) for lo in scenario.loss_outcomes),
            default=0,
        )

    priority_gaps = sorted(
        [s for s in all_scenarios if s.scenario_id in uncovered],
        key=_severity,
        reverse=True,
    )

    return {
        "covered_scenarios": list(covered_ids),
        "uncovered_scenarios": list(uncovered),
        "gap_count": len(uncovered),
        "gap_pct": round(len(uncovered) / len(all_ids) * 100, 1) if all_ids else 0,
        "priority_gaps": [
            {
                "scenario_id": s.scenario_id,
                "name": s.name,
                "asset": s.asset,
                "loss_outcomes": s.loss_outcomes,
                "severity_score": _severity(s),
            }
            for s in priority_gaps[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary(
    mappings: List[ControlMapping],
    unmapped: List[str],
    total_techniques: List[str],
) -> str:
    if not mappings:
        return (
            f"No CIS control mappings confirmed for "
            f"{len(total_techniques)} technique(s). "
            f"Unmapped: {', '.join(unmapped)}."
        )

    scenario_ids = list({m.scenario_id for m in mappings})
    high = sum(1 for m in mappings if m.confidence == "high")
    med  = sum(1 for m in mappings if m.confidence == "medium")
    low  = sum(1 for m in mappings if m.confidence == "low")

    return (
        f"Mapped {len(total_techniques) - len(unmapped)} of {len(total_techniques)} "
        f"techniques to {len(scenario_ids)} CIS risk scenario(s). "
        f"Confidence breakdown: high={high}, medium={med}, low={low}. "
        + (f"Unmapped: {', '.join(unmapped)}." if unmapped else "Full coverage achieved.")
    )
