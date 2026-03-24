"""Spine precheck: DT axis seeds + capability resolution before metrics registry."""

from langchain_core.messages import AIMessage

from app.agents.capabilities.capability_spine import precheck_csod_dt_and_capabilities
from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger


def csod_spine_precheck_node(state: CSOD_State) -> CSOD_State:
    try:
        precheck_csod_dt_and_capabilities(state)
        cap = state.get("capability_resolution") or {}
        _csod_log_step(
            state,
            "csod_spine_precheck",
            "csod_spine_precheck",
            inputs={"intent": state.get("csod_intent")},
            outputs={
                "use_case": cap.get("use_case"),
                "required_capabilities": len(cap.get("required_capability_ids") or []),
                "coverage": cap.get("capability_coverage_ratio"),
            },
        )
        state["messages"].append(
            AIMessage(
                content=(
                    "CSOD spine precheck: decision-tree axes seeded; "
                    f"capability coverage {cap.get('capability_coverage_ratio', 0):.2f}"
                )
            )
        )
    except Exception as e:
        logger.error("csod_spine_precheck_node failed: %s", e, exc_info=True)
        state.setdefault("capability_resolution", {})
        state.setdefault("capability_retrieval_hints", "")
    return state
