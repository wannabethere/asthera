"""
Stage 1: Security Request Classifier — determines what kind of request this is.

Classifies into: detection_only, analysis_only, hybrid, or dashboard.
Also detects domain (security vs lms) and framework signals.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.orchestrator.orchestrator_state import OrchestratorState

logger = logging.getLogger(__name__)


def security_request_classifier_node(state: OrchestratorState) -> OrchestratorState:
    """
    Classify the user request into request_type and detect signals.

    Reads: user_query, compliance_profile
    Writes: request_classification
    """
    user_query = state.get("user_query", "")
    profile = state.get("compliance_profile", {})

    try:
        llm = get_llm(temperature=0)
        prompt = ChatPromptTemplate.from_messages([
            ("system", _CLASSIFIER_SYSTEM_PROMPT),
            ("human", "{input}"),
        ])

        human_msg = f"User query: {user_query}"
        if profile:
            human_msg += f"\n\nCompliance profile context: {json.dumps({k: v for k, v in profile.items() if v}, indent=2)[:2000]}"

        chain = prompt | llm
        response = chain.invoke({"input": human_msg})
        content = response.content if hasattr(response, "content") else str(response)

        classification = _parse_json(content)
        if classification and isinstance(classification, dict):
            state["request_classification"] = classification
        else:
            state["request_classification"] = _heuristic_classify(user_query)

    except Exception as e:
        logger.warning("Request classifier LLM failed, using heuristic: %s", e)
        state["request_classification"] = _heuristic_classify(user_query)

    _log_step(state, "security_request_classifier", state["request_classification"])
    return state


def _heuristic_classify(query: str) -> Dict[str, Any]:
    """Fast heuristic fallback when LLM is unavailable."""
    q = query.lower()

    detection_signals = []
    analysis_signals = []
    framework_signals = []

    # Detection signals
    for kw in ("siem", "rule", "detect", "alert", "playbook", "sigma", "splunk", "kql"):
        if kw in q:
            detection_signals.append(kw)
    # Analysis signals
    for kw in ("metric", "dashboard", "gap", "trend", "kpi", "report", "analysis", "recommend"):
        if kw in q:
            analysis_signals.append(kw)
    # Framework signals
    for fw in ("soc2", "soc 2", "hipaa", "nist", "pci", "gdpr", "iso 27001"):
        if fw in q:
            framework_signals.append(fw.replace(" ", "").upper())

    has_detection = bool(detection_signals)
    has_analysis = bool(analysis_signals)

    if has_detection and has_analysis:
        request_type = "hybrid"
    elif has_detection:
        request_type = "detection_only"
    elif has_analysis:
        request_type = "analysis_only"
    else:
        # Default: if framework mentioned → detection, else analysis
        request_type = "detection_only" if framework_signals else "analysis_only"

    # Dashboard override
    if "dashboard" in q:
        if not has_detection:
            request_type = "dashboard"

    return {
        "request_type": request_type,
        "confidence": 0.70,
        "primary_domain": "security" if (detection_signals or framework_signals) else "lms",
        "framework_signals": framework_signals,
        "analysis_signals": analysis_signals,
        "detection_signals": detection_signals,
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
        "step_name": step_name,
        "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "outputs": {k: v for k, v in outputs.items() if k in ("request_type", "confidence", "primary_domain")},
    })


_CLASSIFIER_SYSTEM_PROMPT = """You are a security request classifier. Given a user query, determine what type of work is needed.

Classify the request into ONE of these types:
- "detection_only": User wants SIEM rules, detection playbooks, alert configurations, or triage procedures. No data analysis.
- "analysis_only": User wants metrics, KPIs, dashboards, gap analysis, or data-driven insights. No detection engineering.
- "hybrid": User wants BOTH detection engineering AND data analysis (e.g., "build detection rules and a monitoring dashboard").
- "dashboard": User specifically wants a visual dashboard (could be analysis or detection context).

Also extract:
- framework_signals: Any compliance frameworks mentioned (SOC2, HIPAA, NIST, PCI, etc.)
- analysis_signals: Keywords suggesting data analysis (metrics, gap, trend, KPI, report, dashboard)
- detection_signals: Keywords suggesting detection engineering (SIEM, rule, detect, alert, playbook, sigma)
- primary_domain: "security" or "lms"

Return JSON:
```json
{
  "request_type": "hybrid",
  "confidence": 0.92,
  "primary_domain": "security",
  "framework_signals": ["SOC2"],
  "analysis_signals": ["dashboard", "metrics"],
  "detection_signals": ["siem", "rules"]
}
```"""
