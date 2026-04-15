"""
intent_splitter.py

LLM-based user query intent decomposition + signal extraction.

For each independent analytical intent the LLM also extracts a set of
**dynamic signals** — key/value pairs whose labels are chosen by the LLM
based on what is analytically meaningful for that specific query.

Examples of signal labels the LLM might emit:
    terminal_metric, urgency, analysis_type, compliance_context, implicit,
    time_bound, data_gap, intervention_type, audience, risk_level …

Both the label names and their values are fully dynamic — the LLM decides
what signals are worth surfacing for each query.

Public API
----------
split_user_intent(user_query, datasource_id) -> List[dict]

Each returned dict shape:
{
    "intent_id":        str,          # "i1" | "i2" | "i3"
    "description":      str,          # concise sub-question
    "analytical_goal":  str,          # insight/decision being sought
    "key_entities":     List[str],    # primary metrics / entities
    "extracted_signals": List[dict],  # [{label: str, value: str}, ...]
}
"""

import json
import logging
import re
from typing import List

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
You are an analytics query decomposition specialist for an LMS (Learning Management System) platform.

Your task has TWO parts for EACH analytical intent:

PART 1 — INTENT DECOMPOSITION
Decompose the user query into 1–3 INDEPENDENT analytical intents.
An analytical intent is a distinct measurement, question, or dimension that requires its own data analysis.

Rules for decomposition:
- Single focused question → exactly 1 intent.
- Multiple separate analytical goals → 2 or 3 intents.
- Never return more than 3 intents, even for very broad queries.
- Do NOT split by filter/dimension variations ("by department" is a scope modifier, not a separate intent).
- intent_id must be a short slug: "i1", "i2", "i3".

PART 2 — SIGNAL EXTRACTION (per intent)
For each intent, extract a list of dynamic key/value signals that capture the
analytically important dimensions of that specific intent.

Rules for signal extraction:
- Choose signal LABELS that are analytically meaningful for THIS specific query.
  Do NOT use a fixed set of labels — invent the right labels for the context.
- Every intent must have 3–6 signals.
- Signals must be specific and information-dense — avoid vague or redundant entries.
- Common useful signal types (use when relevant, add others as needed):
    terminal_metric   — the primary metric being tracked + current/target values if known
    urgency           — deadline or time pressure + what that means analytically
    analysis_type     — specific analytical technique required (gap, trend, cohort, causal…)
    compliance_context — regulatory/audit/policy context shaping the analysis
    implicit          — the unstated real question behind the explicit query
    data_requirement  — what data must be available for this to be answerable
    intervention_type — type of action the insight would drive
    risk_level        — severity or business impact if unresolved
    time_bound        — specific time window or lag structure
    audience          — who will consume the insight and how
- Label names must be snake_case, concise (1–4 words), and self-explanatory.
- Signal values must be 1 sentence max — dense, precise, no filler phrases.

Return ONLY valid JSON — no markdown, no explanation outside the JSON array.
"""

_USER_PROMPT_TEMPLATE = """\
User question: "{user_query}"
Platform/datasource: {datasource_id}

Return a JSON array — one object per analytical intent:

[
  {{
    "intent_id": "i1",
    "description": "<concise description of this specific analytical sub-question>",
    "analytical_goal": "<what insight/decision/measurement this intent is trying to achieve>",
    "key_entities": ["<primary metric or entity>", "..."],
    "extracted_signals": [
      {{"label": "<snake_case_label>", "value": "<dense 1-sentence value>"}},
      ...
    ]
  }}
]

Extract 3–6 signals per intent. Choose the signal labels that best capture
the analytically important dimensions of THAT specific intent.
"""


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    from app.core.provider import get_llm_for_type, LlmType
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm_for_type(LlmType.EXECUTOR, temperature=0.0)
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    return response.content if hasattr(response, "content") else str(response)


def _parse_intent_list(raw: str) -> list:
    """Extract JSON array from LLM response, stripping any markdown fences."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            logger.warning("Intent splitter: unparseable JSON (%d chars)", len(raw))
            return []


def _normalise_signals(raw_signals: object) -> List[dict]:
    """
    Normalise extracted_signals to List[{label: str, value: str}].
    Accepts list of dicts or any other shape the LLM might return.
    """
    if not isinstance(raw_signals, list):
        return []
    result = []
    for item in raw_signals:
        if isinstance(item, dict) and item.get("label") and item.get("value"):
            result.append({
                "label": str(item["label"]).strip().lower().replace(" ", "_"),
                "value": str(item["value"]).strip(),
            })
    return result


def split_user_intent(user_query: str, datasource_id: str = "") -> List[dict]:
    """
    Decompose user_query into 1–3 independent analytical intents, each with
    dynamic extracted signals.

    Returns a list of dicts, each with keys:
        intent_id, description, analytical_goal, key_entities, extracted_signals

    Falls back to a single passthrough intent on any error.
    """
    if not user_query or not user_query.strip():
        logger.warning("split_user_intent called with empty query — returning passthrough intent")
        return [_passthrough_intent(user_query)]

    prompt = _USER_PROMPT_TEMPLATE.format(
        user_query=user_query,
        datasource_id=datasource_id or "cornerstone",
    )

    try:
        raw = _call_llm(_SYSTEM_PROMPT, prompt)
        logger.debug("Intent splitter raw response:\n%s", raw)
        intents = _parse_intent_list(raw)
    except Exception as exc:
        logger.exception("Intent splitter LLM call failed: %s", exc)
        return [_passthrough_intent(user_query)]

    if not intents or not isinstance(intents, list):
        logger.warning("Intent splitter returned no intents — falling back to passthrough")
        return [_passthrough_intent(user_query)]

    result = []
    for i, item in enumerate(intents[:3]):
        if not isinstance(item, dict):
            continue
        result.append({
            "intent_id": item.get("intent_id") or f"i{i + 1}",
            "description": item.get("description", user_query),
            "analytical_goal": item.get("analytical_goal", ""),
            "key_entities": item.get("key_entities") or [],
            "extracted_signals": _normalise_signals(item.get("extracted_signals")),
        })

    if not result:
        return [_passthrough_intent(user_query)]

    logger.info(
        "Intent splitter: %d intent(s) with signals %s for query %r",
        len(result),
        [[s["label"] for s in r["extracted_signals"]] for r in result],
        user_query[:80],
    )
    return result


def _passthrough_intent(user_query: str) -> dict:
    """Single-intent fallback — preserves original query as-is, no signals."""
    return {
        "intent_id": "i1",
        "description": user_query,
        "analytical_goal": user_query,
        "key_entities": [],
        "extracted_signals": [],
    }
