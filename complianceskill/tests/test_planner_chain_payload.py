"""Planner→downstream invoke payload matches between service and registration helper."""

from app.services.agent_invocation_service import build_planner_chain_invoke_payload
from app.services.agent_registration import build_csod_chain_invoke_payload_after_planner


def test_build_planner_chain_invoke_payload_shape():
    po = {
        "user_query": "track training metrics",
        "csod_intent": "metrics_advice",
        "compliance_profile": {"framework": "soc2"},
        "selected_data_sources": [{"id": "ds1"}],
        "active_project_id": "proj-1",
    }
    p = build_planner_chain_invoke_payload(
        po, thread_id="thread-a", original_run_id="run99", original_step_id="step_2"
    )
    assert p["input"] == "track training metrics"
    assert p["thread_id"] == "thread-a"
    assert p["run_id"] == "run99_chain"
    assert p["step_id"] == "step_2_chain"
    assert p["step_index"] == 1
    assert p["planner_output"] is po
    assert p["skip_conversation_phase0"] is True
    assert p["csod_intent"] == "metrics_advice"
    assert p["compliance_profile"] == {"framework": "soc2"}
    assert p["active_project_id"] == "proj-1"


def test_registration_wrapper_matches_service():
    po = {"user_query": "q"}
    a = build_planner_chain_invoke_payload(po, thread_id="t", original_run_id="r")
    b = build_csod_chain_invoke_payload_after_planner(po, thread_id="t", original_run_id="r")
    assert a == b
