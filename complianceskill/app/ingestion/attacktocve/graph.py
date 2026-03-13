"""
ATT&CK → CIS Control Mapping LangGraph
=======================================

Graph topology
--------------

  [enrich_attack]
       │
  [build_query]
       │
  [retrieve_scenarios]
       │ (conditional)
       ├── scenarios found ──→ [map_controls]
       └── no results       ──→ [yaml_fallback] → [map_controls]
                                                        │
                                                 [validate_mappings]
                                                        │
                                                   [output_node]
                                                        │
                                                      END

Usage
-----
    from graph import build_graph, VectorStoreConfig, run_mapping

    config = VectorStoreConfig(backend="chroma", collection="cis_controls")
    graph  = build_graph(config, yaml_path="cis_controls_v8_1_risk_controls.yaml")
    result = run_mapping(graph, "T1078")
    print(result["output_summary"])
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from .state import AttackControlState
    from .nodes import (
        enrich_attack_node,
        build_query_node,
        retrieve_scenarios_node,
        yaml_fallback_node,
        map_controls_node,
        validate_mappings_node,
        output_node,
        should_use_fallback,
    )
    from .control_loader import CISControlRegistry, load_cis_scenarios
    from .vectorstore_retrieval import VectorStoreConfig
except ImportError:
    # Fallback for when run as script - import directly from files
    try:
        from state import AttackControlState
        from nodes import (
            enrich_attack_node,
            build_query_node,
            retrieve_scenarios_node,
            yaml_fallback_node,
            map_controls_node,
            validate_mappings_node,
            output_node,
            should_use_fallback,
        )
        from control_loader import CISControlRegistry, load_cis_scenarios
        from vectorstore_retrieval import VectorStoreConfig
    except ImportError:
        # Final fallback - use absolute imports
        from app.ingestion.attacktocve.state import AttackControlState
        from app.ingestion.attacktocve.nodes import (
            enrich_attack_node,
            build_query_node,
            retrieve_scenarios_node,
            yaml_fallback_node,
            map_controls_node,
            validate_mappings_node,
            output_node,
            should_use_fallback,
        )
        from app.ingestion.attacktocve.control_loader import CISControlRegistry, load_cis_scenarios
        from app.ingestion.attacktocve.vectorstore_retrieval import VectorStoreConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(
    vs_config: VectorStoreConfig,
    yaml_path: str = "cis_controls_v8_1_risk_controls.yaml",
    framework_id: Optional[str] = None,
) -> StateGraph:
    """
    Assemble and compile the LangGraph for ATT&CK → CIS control mapping.

    Args:
        vs_config  : Vector store backend config (Qdrant or Chroma).
        yaml_path  : Path to the CIS Controls YAML file (for fallback + registry).
        framework_id: Optional framework identifier (e.g., "cis_controls_v8_1")

    Returns:
        Compiled StateGraph ready to invoke.
    """
    # Get framework info for prompts
    try:
        from .prompts import get_framework_info_from_yaml_path, get_framework_preset
        if framework_id:
            framework_info = get_framework_preset(framework_id)
        else:
            framework_info = get_framework_info_from_yaml_path(yaml_path)
    except ImportError:
        from prompts import get_framework_info_from_yaml_path, get_framework_preset
        if framework_id:
            framework_info = get_framework_preset(framework_id)
        else:
            framework_info = get_framework_info_from_yaml_path(yaml_path)
    
    # Store framework info for nodes to use
    _framework_name = framework_info.get("framework_name", "CIS Controls v8.1")
    _control_id_label = framework_info.get("control_id_label", "CIS-RISK-NNN")
    
    # Shared registry – lives for the lifetime of the graph instance
    scenarios = load_cis_scenarios(yaml_path)
    registry = CISControlRegistry(scenarios)

    # ── Bind dependencies into nodes ──────────────────────────────────────
    retrieve_node = functools.partial(
        retrieve_scenarios_node, vs_config=vs_config
    )
    fallback_node = functools.partial(
        yaml_fallback_node, registry=registry
    )
    finish_node = functools.partial(
        output_node, registry=registry
    )
    
    # Store framework info in a closure for nodes to access
    def _get_framework_info():
        return {"framework_name": _framework_name, "control_id_label": _control_id_label}
    
    # Make framework info available to nodes via a module-level variable
    # (Nodes will access it through a helper function)
    try:
        import nodes as nodes_module
    except ImportError:
        from . import nodes as nodes_module
    nodes_module._graph_framework_info = _get_framework_info

    # ── Build graph ────────────────────────────────────────────────────────
    workflow = StateGraph(AttackControlState)

    workflow.add_node("enrich_attack",       enrich_attack_node)
    workflow.add_node("build_query",         build_query_node)
    workflow.add_node("retrieve_scenarios",  retrieve_node)
    workflow.add_node("yaml_fallback",       fallback_node)
    workflow.add_node("map_controls",        map_controls_node)
    workflow.add_node("validate_mappings",   validate_mappings_node)
    workflow.add_node("output",              finish_node)

    # ── Edges ──────────────────────────────────────────────────────────────
    workflow.set_entry_point("enrich_attack")

    workflow.add_edge("enrich_attack",      "build_query")
    workflow.add_edge("build_query",        "retrieve_scenarios")

    # Conditional: vector store miss → fallback
    workflow.add_conditional_edges(
        "retrieve_scenarios",
        should_use_fallback,
        {
            "map_controls":  "map_controls",
            "yaml_fallback": "yaml_fallback",
        },
    )

    workflow.add_edge("yaml_fallback",      "map_controls")
    workflow.add_edge("map_controls",       "validate_mappings")
    workflow.add_edge("validate_mappings",  "output")
    workflow.add_edge("output",             END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

def run_mapping(
    graph,
    technique_id: str,
    scenario_filter: Optional[str] = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    Run the mapping pipeline for a single ATT&CK technique.

    Args:
        graph           : Compiled graph from build_graph().
        technique_id    : e.g. "T1078", "T1059.001"
        scenario_filter : Optional CIS asset domain to restrict retrieval.
        stream          : If True, stream node outputs to stdout.

    Returns:
        Final graph state dict.
    """
    initial_state: AttackControlState = {
        "technique_id": technique_id,
        "scenario_filter": scenario_filter,
        "attack_detail": None,
        "enrich_error": None,
        "retrieved_scenarios": [],
        "retrieval_scores": [],
        "retrieval_source": "",
        "raw_mappings": [],
        "mapping_rationale": "",
        "validation_result": None,
        "final_mappings": [],
        "enriched_scenarios": [],
        "output_summary": "",
        "error": None,
        "current_node": "start",
        "iteration_count": 0,
    }

    if stream:
        final_state = {}
        for chunk in graph.stream(initial_state):
            node_name = list(chunk.keys())[0]
            node_output = chunk[node_name]
            logger.info(f"── Node: {node_name} ──")
            if node_name == "output" and "output_summary" in node_output:
                print(f"\n[{node_name}] {node_output.get('output_summary', '')}\n")
            final_state.update(node_output)
        return final_state
    else:
        return graph.invoke(initial_state)


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_batch_mapping(
    graph,
    technique_ids: list[str],
    scenario_filter: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Run the mapping pipeline for multiple ATT&CK techniques.

    Returns:
        Dict mapping technique_id → final state dict.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for tid in technique_ids:
        logger.info(f"Processing technique {tid}")
        try:
            state = run_mapping(graph, tid, scenario_filter=scenario_filter)
            results[tid] = state
        except Exception as exc:
            logger.error(f"Failed for {tid}: {exc}")
            results[tid] = {"error": str(exc), "technique_id": tid}
    return results
