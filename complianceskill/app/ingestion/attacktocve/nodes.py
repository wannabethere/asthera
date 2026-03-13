"""
LangGraph Nodes
===============
Each function takes the graph state and returns a partial state update.

Node pipeline:
  enrich_attack_node
    → build_query_node
      → retrieve_scenarios_node
        → map_controls_node
          → validate_mappings_node
            → output_node
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from .state import (
        AttackControlState,
        ATTACKTechniqueDetail,
        CISRiskScenario,
        ControlMapping,
        ValidationResult,
    )
    from .prompts import (
        ATTACK_QUERY_BUILDER,
        CONTROL_MAPPING_SYSTEM,
        CONTROL_MAPPING_USER,
        VALIDATION_SYSTEM,
        VALIDATION_USER,
        SUMMARY_SYSTEM,
        SUMMARY_USER,
    )
    from .attack_enrichment import ATTACKEnrichmentTool
    from .vectorstore_retrieval import VectorStoreRetriever, VectorStoreConfig
    from .control_loader import CISControlRegistry
except ImportError:
    # Fallback for when run as script - import directly from files
    try:
        from state import (
            AttackControlState,
            ATTACKTechniqueDetail,
            CISRiskScenario,
            ControlMapping,
            ValidationResult,
        )
        from prompts import (
            ATTACK_QUERY_BUILDER,
            CONTROL_MAPPING_SYSTEM,
            CONTROL_MAPPING_USER,
            VALIDATION_SYSTEM,
            VALIDATION_USER,
            SUMMARY_SYSTEM,
            SUMMARY_USER,
        )
        from attack_enrichment import ATTACKEnrichmentTool
        from vectorstore_retrieval import VectorStoreRetriever, VectorStoreConfig
        from control_loader import CISControlRegistry
    except ImportError:
        # Final fallback - use absolute imports
        from app.ingestion.attacktocve.state import (
            AttackControlState,
            ATTACKTechniqueDetail,
            CISRiskScenario,
            ControlMapping,
            ValidationResult,
        )
        from app.ingestion.attacktocve.prompts import (
            ATTACK_QUERY_BUILDER,
            CONTROL_MAPPING_SYSTEM,
            CONTROL_MAPPING_USER,
            VALIDATION_SYSTEM,
            VALIDATION_USER,
            SUMMARY_SYSTEM,
            SUMMARY_USER,
        )
        from app.ingestion.attacktocve.attack_enrichment import ATTACKEnrichmentTool
        from app.ingestion.attacktocve.vectorstore_retrieval import VectorStoreRetriever, VectorStoreConfig
        from app.ingestion.attacktocve.control_loader import CISControlRegistry

logger = logging.getLogger(__name__)

# Framework info set by build_graph (accessed by nodes)
_graph_framework_info = None


def _get_framework_info() -> dict:
    """Get framework info from graph builder or return defaults."""
    global _graph_framework_info
    if _graph_framework_info:
        return _graph_framework_info()
    # Defaults for backward compatibility
    return {"framework_name": "CIS Controls v8.1", "control_id_label": "CIS-RISK-NNN"}


# ---------------------------------------------------------------------------
# LLM singleton helpers
# ---------------------------------------------------------------------------

def _get_llm(temperature: float = 0.0, model: str = "gpt-4o-mini") -> ChatOpenAI:
    return ChatOpenAI(model=model, temperature=temperature)


# ---------------------------------------------------------------------------
# Node 1 – ATT&CK Enrichment
# ---------------------------------------------------------------------------

def enrich_attack_node(state: AttackControlState) -> Dict[str, Any]:
    """
    Fetch full ATT&CK technique metadata.
    Writes: attack_detail | enrich_error
    """
    technique_id = state["technique_id"]
    logger.info(f"[enrich_attack] Fetching technique {technique_id}")

    try:
        tool = ATTACKEnrichmentTool()
        detail = tool.get_technique(technique_id)
        return {
            "attack_detail": detail,
            "enrich_error": None,
            "current_node": "enrich_attack",
        }
    except Exception as exc:
        logger.error(f"[enrich_attack] Error: {exc}")
        return {
            "attack_detail": None,
            "enrich_error": str(exc),
            "current_node": "enrich_attack",
            "error": f"ATT&CK enrichment failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Node 2 – Build Vector Store Query
# ---------------------------------------------------------------------------

def build_query_node(state: AttackControlState) -> Dict[str, Any]:
    """
    Ask LLM to formulate an optimal semantic search query from technique metadata.
    Writes: _vs_query (internal, passed forward as retrieval query)
    """
    detail: ATTACKTechniqueDetail = state.get("attack_detail")
    if detail is None:
        # Fall back to technique ID as query
        return {"_vs_query": state["technique_id"], "current_node": "build_query"}

    # Get framework info for prompt
    framework_info = _get_framework_info()

    llm = _get_llm(temperature=0.3)
    prompt = ATTACK_QUERY_BUILDER.format(
        framework_name=framework_info["framework_name"],
        technique_id=detail.technique_id,
        technique_name=detail.name,
        tactics=", ".join(detail.tactics) or "N/A",
        platforms=", ".join(detail.platforms) or "N/A",
        description=detail.description[:1200],
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    query = response.content.strip()
    logger.info(f"[build_query] Query: {query[:120]}…")
    return {"_vs_query": query, "current_node": "build_query"}


# ---------------------------------------------------------------------------
# Node 3 – Retrieve Scenarios from Vector Store
# ---------------------------------------------------------------------------

def retrieve_scenarios_node(
    state: AttackControlState,
    vs_config: VectorStoreConfig,
) -> Dict[str, Any]:
    """
    Semantic retrieval of top-k CIS risk scenarios.
    Writes: retrieved_scenarios, retrieval_scores, retrieval_source
    """
    query: str = state.get("_vs_query", state["technique_id"])
    asset_filter: Optional[str] = state.get("scenario_filter")
    # Get framework_id from state (set by graph)
    framework_id: Optional[str] = state.get("framework_id")

    logger.info(f"[retrieve_scenarios] Querying {vs_config.backend} with asset_filter={asset_filter}, framework={framework_id}")

    try:
        retriever = VectorStoreRetriever(vs_config)
        results = retriever.retrieve(query, asset_filter=asset_filter, framework_filter=framework_id)

        if not results:
            logger.warning("[retrieve_scenarios] No results from vector store; empty list returned")

        scenarios = []
        scores = []
        for r in results:
            scenarios.append(
                CISRiskScenario(
                    scenario_id=r.scenario_id,
                    name=r.name,
                    asset=r.asset,
                    trigger=r.trigger,
                    loss_outcomes=r.loss_outcomes,
                    description=r.description,
                    controls=r.controls,
                )
            )
            scores.append(r.score)

        return {
            "retrieved_scenarios": scenarios,
            "retrieval_scores": scores,
            "retrieval_source": vs_config.backend.value,
            "current_node": "retrieve_scenarios",
        }
    except Exception as exc:
        logger.error(f"[retrieve_scenarios] Error: {exc}")
        return {
            "retrieved_scenarios": [],
            "retrieval_scores": [],
            "retrieval_source": "error",
            "current_node": "retrieve_scenarios",
            "error": f"Vector store retrieval failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Node 4 – YAML Fallback Retrieval (if vector store unavailable)
# ---------------------------------------------------------------------------

def yaml_fallback_node(
    state: AttackControlState,
    registry: CISControlRegistry,
) -> Dict[str, Any]:
    """
    Keyword-based retrieval from the in-memory CIS registry.
    Used when vector store is not yet populated.
    Writes: retrieved_scenarios, retrieval_scores, retrieval_source
    """
    detail: Optional[ATTACKTechniqueDetail] = state.get("attack_detail")
    keywords = []
    if detail:
        keywords = [detail.name] + detail.tactics + detail.platforms[:2]
    else:
        keywords = [state["technique_id"]]

    all_found: Dict[str, CISRiskScenario] = {}
    for kw in keywords:
        for s in registry.search(kw):
            all_found[s.scenario_id] = s

    # Also grab all if nothing found
    if not all_found:
        all_found = {s.scenario_id: s for s in registry.all()[:8]}

    scenarios = list(all_found.values())[:8]
    scores = [0.5] * len(scenarios)  # No real scores for keyword search

    return {
        "retrieved_scenarios": scenarios,
        "retrieval_scores": scores,
        "retrieval_source": "yaml_fallback",
        "current_node": "yaml_fallback",
    }


# ---------------------------------------------------------------------------
# Node 5 – LLM Control Mapping
# ---------------------------------------------------------------------------

def map_controls_node(state: AttackControlState) -> Dict[str, Any]:
    """
    Core LLM call: maps ATT&CK technique to CIS scenarios.
    Writes: raw_mappings, mapping_rationale
    """
    detail: Optional[ATTACKTechniqueDetail] = state.get("attack_detail")
    scenarios: List[CISRiskScenario] = state.get("retrieved_scenarios", [])

    if not scenarios:
        logger.warning("[map_controls] No scenarios to map")
        return {
            "raw_mappings": [],
            "mapping_rationale": "No candidate scenarios retrieved.",
            "current_node": "map_controls",
        }

    # Serialize scenarios for LLM
    scenarios_data = [
        {
            "scenario_id": s.scenario_id,
            "name": s.name,
            "asset": s.asset,
            "trigger": s.trigger,
            "loss_outcomes": s.loss_outcomes,
            "description": s.description[:600] if s.description else "",  # keep prompt manageable
        }
        for s in scenarios
    ]

    # Get framework info for prompts
    framework_info = _get_framework_info()

    user_prompt = CONTROL_MAPPING_USER.format(
        framework_name=framework_info["framework_name"],
        technique_id=detail.technique_id if detail else state["technique_id"],
        technique_name=detail.name if detail else "Unknown",
        tactics=", ".join(detail.tactics) if detail else "N/A",
        platforms=", ".join(detail.platforms) if detail else "N/A",
        description=(detail.description[:1000] if detail else ""),
        mitigations=json.dumps([m.get("name", "") for m in (detail.mitigations if detail else [])]),
        data_sources=", ".join(detail.data_sources if detail else []),
        top_k=len(scenarios),
        scenarios_json=json.dumps(scenarios_data, indent=2),
    )

    system_prompt = CONTROL_MAPPING_SYSTEM.format(
        framework_name=framework_info["framework_name"],
        control_id_label=framework_info["control_id_label"],
    )

    llm = _get_llm(temperature=0.1, model="gpt-4o")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    logger.info(f"[map_controls] Calling LLM for {len(scenarios)} candidate scenarios")
    response = llm.invoke(messages)
    raw_text = response.content.strip()

    # Parse JSON
    mappings: List[ControlMapping] = []
    try:
        parsed = json.loads(raw_text)
        for item in parsed:
            # Ensure technique_id is set
            item["technique_id"] = item.get(
                "technique_id", state["technique_id"]
            )
            try:
                mappings.append(ControlMapping(**item))
            except Exception as e:
                logger.warning(f"[map_controls] Skipping malformed mapping: {e}")
    except json.JSONDecodeError as exc:
        logger.error(f"[map_controls] JSON parse error: {exc}\nRaw: {raw_text[:500]}")
        return {
            "raw_mappings": [],
            "mapping_rationale": f"LLM returned invalid JSON: {exc}",
            "current_node": "map_controls",
            "error": "mapping_json_parse_error",
        }

    rationale = f"Mapped {len(mappings)} scenarios from {len(scenarios)} candidates."
    return {
        "raw_mappings": mappings,
        "mapping_rationale": rationale,
        "current_node": "map_controls",
    }


# ---------------------------------------------------------------------------
# Node 6 – Validation
# ---------------------------------------------------------------------------

def validate_mappings_node(state: AttackControlState) -> Dict[str, Any]:
    """
    LLM-based validation pass.  Corrects scores and removes bad mappings.
    Writes: validation_result
    """
    raw_mappings: List[ControlMapping] = state.get("raw_mappings", [])
    detail: Optional[ATTACKTechniqueDetail] = state.get("attack_detail")

    if not raw_mappings:
        return {
            "validation_result": ValidationResult(
                is_valid=True,
                issues=["No mappings to validate"],
                corrected_mappings=[],
                validation_notes="Input was empty.",
            ),
            "current_node": "validate_mappings",
        }

    technique_summary = (
        f"{detail.technique_id} – {detail.name}\n"
        f"Tactics: {', '.join(detail.tactics)}\n"
        f"Description snippet: {detail.description[:400] if detail.description else 'N/A'}"
        if detail
        else state["technique_id"]
    )

    # Get framework info for prompts
    framework_info = _get_framework_info()

    user_prompt = VALIDATION_USER.format(
        framework_name=framework_info["framework_name"],
        technique_summary=technique_summary,
        raw_mappings_json=json.dumps(
            [m.model_dump() for m in raw_mappings], indent=2
        ),
    )

    system_prompt = VALIDATION_SYSTEM.format(
        framework_name=framework_info["framework_name"],
    )

    llm = _get_llm(temperature=0.0, model="gpt-4o")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    logger.info(f"[validate_mappings] Validating {len(raw_mappings)} mappings")
    response = llm.invoke(messages)
    raw_text = response.content.strip()

    try:
        parsed = json.loads(raw_text)
        corrected = [ControlMapping(**m) for m in parsed.get("corrected_mappings", [])]
        result = ValidationResult(
            is_valid=parsed.get("is_valid", True),
            issues=parsed.get("issues", []),
            corrected_mappings=corrected,
            validation_notes=parsed.get("validation_notes", ""),
        )
    except Exception as exc:
        logger.error(f"[validate_mappings] Parse error: {exc}")
        result = ValidationResult(
            is_valid=False,
            issues=[str(exc)],
            corrected_mappings=raw_mappings,  # pass through if parse fails
            validation_notes="Validation parse failed – using raw mappings.",
        )

    return {"validation_result": result, "current_node": "validate_mappings"}


# ---------------------------------------------------------------------------
# Node 7 – Output / Registry Update
# ---------------------------------------------------------------------------

def output_node(
    state: AttackControlState,
    registry: Optional[CISControlRegistry] = None,
) -> Dict[str, Any]:
    """
    Finalise mappings, update the CIS registry, and generate a summary.
    Writes: final_mappings, enriched_scenarios, output_summary
    """
    validation: Optional[ValidationResult] = state.get("validation_result")
    detail: Optional[ATTACKTechniqueDetail] = state.get("attack_detail")

    # Use validated mappings if available, else raw
    if validation and validation.corrected_mappings:
        final = validation.corrected_mappings
    else:
        final = state.get("raw_mappings", [])

    # Sort by relevance score descending
    final = sorted(final, key=lambda m: m.relevance_score, reverse=True)

    # Update registry
    enriched: List[CISRiskScenario] = []
    if registry:
        for mapping in final:
            registry.update_controls(mapping.scenario_id, [mapping.technique_id])
            scenario = registry.get(mapping.scenario_id)
            if scenario:
                enriched.append(scenario)

    # Generate summary
    summary = _generate_summary(state, final)

    logger.info(
        f"[output] Final: {len(final)} mappings | "
        f"Coverage: {registry.coverage_report() if registry else 'N/A'}"
    )

    return {
        "final_mappings": final,
        "enriched_scenarios": enriched,
        "output_summary": summary,
        "current_node": "output",
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def _generate_summary(
    state: AttackControlState,
    final: List[ControlMapping],
) -> str:
    detail: Optional[ATTACKTechniqueDetail] = state.get("attack_detail")
    if not final or not detail:
        return f"No mappings produced for {state['technique_id']}."

    # Get framework info for prompts
    framework_info = _get_framework_info()

    llm = _get_llm(temperature=0.3, model="gpt-4o-mini")
    user_prompt = SUMMARY_USER.format(
        framework_name=framework_info["framework_name"],
        technique_id=detail.technique_id,
        technique_name=detail.name,
        tactics=", ".join(detail.tactics),
        final_mappings_json=json.dumps(
            [{"scenario_id": m.scenario_id, "name": m.scenario_name,
              "confidence": m.confidence, "rationale": m.rationale}
             for m in final],
            indent=2,
        ),
    )
    system_prompt = SUMMARY_SYSTEM.format(
        framework_name=framework_info["framework_name"],
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    return llm.invoke(messages).content.strip()


# ---------------------------------------------------------------------------
# Edge condition – route after retrieval
# ---------------------------------------------------------------------------

def should_use_fallback(state: AttackControlState) -> str:
    """Conditional edge: route to yaml_fallback if vector store returned nothing."""
    if not state.get("retrieved_scenarios"):
        return "yaml_fallback"
    return "map_controls"
