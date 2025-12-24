import pytest
from unittest.mock import Mock


def test_convert_service_response_to_compatibility_clarification_required():
    """Ensure clarification-required orchestrator results are surfaced in compatibility responses."""
    from app.services.writers.alert_service import (
        AlertServiceCompatibility,
        AlertResponse,
        AlertRequestType,
    )

    wrapper = AlertServiceCompatibility(alert_service=Mock(), default_project_id="default_project")

    service_response = AlertResponse(
        success=True,
        request_type=AlertRequestType.SINGLE_ALERT,
        result={
            "status": "clarification_required",
            "project_id": "csod_risk_attrition",
            "query_index": 0,
            "clarification": {
                "questions": ["Which metric should trigger the alert?"],
                "ambiguous_elements": ["Two conditions were provided"],
                "suggested_improvements": ["Specify whether to alert on count, risk score, or both"],
            },
        },
        metadata={"session_id": "sid"},
    )

    compat = wrapper.convert_service_response_to_compatibility(service_response)
    assert compat.type == "clarification_required"
    assert compat.service_created is False
    assert "Which metric should trigger the alert?" in compat.summary


@pytest.mark.asyncio
async def test_sql_to_alert_agent_refine_handles_missing_critique_notes_with_clarification():
    """Regression: avoid KeyError('critique_notes') and return clarification instead."""
    from app.agents.nodes.writers.alerts_agent import SQLToAlertAgent
    from app.agents.nodes.writers.alert_models import SQLAlertRequest, SQLAnalysis, AlertClarification

    class DummyLLM:
        async def ainvoke(self, input):
            return {}

        def invoke(self, input):
            return {}

    agent = SQLToAlertAgent(
        sql_parser_llm=DummyLLM(),
        alert_generator_llm=DummyLLM(),
        critic_llm=DummyLLM(),
        refiner_llm=DummyLLM(),
    )

    request = SQLAlertRequest(
        sql="SELECT 1",
        query="q",
        project_id="p",
        alert_request="Alert me when something happens",
    )
    sql_analysis = SQLAnalysis(
        tables=[],
        columns=[],
        metrics=[],
        dimensions=[],
        filters=[],
        aggregations=[],
    )

    feed_config = AlertClarification(
        clarification_questions=["Which metric should trigger the alert?"],
        ambiguous_elements=["Two alert conditions were specified"],
        suggested_improvements=["Specify whether to alert on count, risk score, or both"],
    )

    # Critique payload intentionally omits critique_notes/suggestions keys
    critique = {
        "is_valid": False,
        "needs_clarification": True,
        "clarification_questions": ["Which metric should trigger the alert?"],
        "ambiguous_elements": ["Two alert conditions were specified"],
    }

    result = await agent._refine_alert_configuration(
        {
            "request": request,
            "sql_analysis": sql_analysis,
            "feed_configuration": feed_config,
            "critique": critique,
        }
    )

    assert result.feed_configuration is None
    assert result.clarification is not None
    assert result.clarification.needs_clarification is True

