"""
Guardrails: classifier catalog + pipeline aliases stay aligned with
examples/lexy_conversation_flows.json so Lexy UI / pipeline HTML stay consistent.
"""
import json
from pathlib import Path

import pytest

from app.agents.csod.intent_config import (
    ALLOWED_CSOD_ANALYSIS_INTENTS,
    INTENT_CATALOG_ENTRIES,
    INTENT_PIPELINE_ALIASES,
    STAGE_1_INTENT_EXAMPLES_PATH,
    build_stage_1_intent_from_classifier,
    get_dt_config_for_intent,
    resolve_pipeline_intent,
)

_LEXY_FLOWS = Path(__file__).resolve().parent.parent / "examples" / "lexy_conversation_flows.json"
_STAGE1_EXAMPLES = STAGE_1_INTENT_EXAMPLES_PATH


def _load_lexy_conversations():
    data = json.loads(_LEXY_FLOWS.read_text(encoding="utf-8"))
    return data["conversations"]


@pytest.fixture(scope="module")
def lexy_conversations():
    assert _LEXY_FLOWS.is_file(), f"Missing {_LEXY_FLOWS}"
    return _load_lexy_conversations()


def test_every_lexy_stage1_intent_in_classifier_catalog(lexy_conversations):
    """Each demo conversation's stage_1 intent must be a valid classifier id."""
    for conv in lexy_conversations:
        s1 = conv.get("stage_1_intent") or {}
        reg = s1.get("intent")
        assert reg, f"{conv.get('id')}: missing stage_1_intent.intent"
        assert reg in ALLOWED_CSOD_ANALYSIS_INTENTS, (
            f"{conv.get('id')}: intent {reg!r} not in INTENT_CATALOG_ENTRIES — "
            "add it or fix lexy_conversation_flows.json"
        )


def test_lexy_to_pipeline_resolution_matches_expectations(lexy_conversations):
    """Registry labels map to the canonical intents the executor registry uses."""
    expected = {
        "compliance_gap_close": "gap_analysis",
        "cohort_analysis": "cohort_analysis",
        "dashboard_generation_for_persona": "dashboard_generation_for_persona",
        "predictive_risk_analysis": "predictive_risk_analysis",
        "current_state_metric_lookup": "metrics_dashboard_plan",
        "anomaly_detection": "anomaly_detection",
        "training_plan_dashboard": "dashboard_generation_for_persona",
    }
    seen = set()
    for conv in lexy_conversations:
        s1 = conv.get("stage_1_intent") or {}
        reg = s1["intent"]
        seen.add(reg)
        canon = resolve_pipeline_intent(reg)
        assert reg in expected, f"Add {reg} to expected map for conv {conv.get('id')}"
        assert canon == expected[reg], (
            f"{conv.get('id')}: resolve_pipeline_intent({reg!r}) → {canon!r}, "
            f"expected {expected[reg]!r}"
        )

    assert seen == set(expected.keys()), f"Lexy JSON intents changed: {seen ^ set(expected.keys())}"


def test_alias_table_matches_intent_config():
    """INTENT_PIPELINE_ALIASES is the single source for non-identity mappings."""
    assert INTENT_PIPELINE_ALIASES["compliance_gap_close"] == "gap_analysis"
    assert INTENT_PIPELINE_ALIASES["current_state_metric_lookup"] == "metrics_dashboard_plan"
    assert INTENT_PIPELINE_ALIASES["training_plan_dashboard"] == "dashboard_generation_for_persona"


def test_lexy_registry_intents_have_dt_config_when_pipeline_expects_dt():
    """Aliased Lexy ids inherit DT params from their canonical pipeline intent."""
    assert get_dt_config_for_intent("compliance_gap_close").get("requires_target_value") is True
    assert get_dt_config_for_intent("current_state_metric_lookup")
    assert get_dt_config_for_intent("training_plan_dashboard")


def test_build_stage_1_preserves_lexy_shape():
    result = {
        "confidence_score": 0.93,
        "intent_signals": ["mentions next Friday", "deadline risk"],
        "stage_1_intent": {
            "routing": "full_spine",
            "tags": ["risk_prediction"],
            "signals": [{"key": "time_horizon", "value": "7-day window"}],
        },
    }
    s1 = build_stage_1_intent_from_classifier(result, "predictive_risk_analysis")
    assert s1["intent"] == "predictive_risk_analysis"
    assert s1["confidence"] == 0.93
    assert s1["routing"] == "full_spine"
    assert any(sig["key"] == "time_horizon" for sig in s1["signals"])


def test_stage_1_examples_file_covers_catalog():
    """Static stage_1 examples JSON aligns with classifier catalog keys."""
    assert _STAGE1_EXAMPLES.is_file()
    raw = json.loads(_STAGE1_EXAMPLES.read_text(encoding="utf-8"))
    keys = set(raw.get("intents", {}))
    assert keys == set(INTENT_CATALOG_ENTRIES.keys()), (
        f"stage_1_intent_examples.json keys mismatch INTENT_CATALOG_ENTRIES: "
        f"only in examples {keys - set(INTENT_CATALOG_ENTRIES)} "
        f"only in catalog {set(INTENT_CATALOG_ENTRIES) - keys}"
    )
    for iid, block in raw["intents"].items():
        assert block.get("examples"), f"{iid}: no examples"
        for ex in block["examples"]:
            s1 = ex.get("stage_1_intent") or {}
            assert s1.get("intent") == iid, (ex.get("example_id"), s1.get("intent"), iid)
            assert s1.get("signals"), f"{ex.get('example_id')}: empty signals"


def test_catalog_has_lexy_example_questions():
    """Golden questions from lexy_conversation_flows appear in catalog examples."""
    by_id = INTENT_CATALOG_ENTRIES
    assert any(
        "SOC2 audit in 30 days" in ex for ex in by_id["compliance_gap_close"]["examples"]
    )
    assert any(
        "next Friday" in ex or "SOC2 training deadline" in ex
        for ex in by_id["predictive_risk_analysis"]["examples"]
    )
    assert any(
        "completion rate this week" in ex.lower()
        for ex in by_id["current_state_metric_lookup"]["examples"]
    )
    assert any(
        "Procurement" in ex for ex in by_id["training_plan_dashboard"]["examples"]
    )
