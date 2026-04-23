"""CSOD Question Rephraser node.

Given a user question + resolved project IDs / schemas / causal graph, this node:
  1. Sub-classifies the question as DIRECT_SQL, TREND_ANALYTICAL, or ALERT_RCA.
  2. Rephrases it into ONE precise, schema-grounded NL question.
  3. Resolves which project IDs (source tables) the question should come from.
  4. For ALERT_RCA, generates a causal explanation (graph structure for UI) while
     keeping the rephrased question itself graph-structure-free.

State inputs:
    user_query, csod_intent, csod_causal_nodes, csod_causal_edges,
    csod_causal_graph_metadata, causal_signals, csod_resolved_project_ids

State output:
    csod_question_rephraser_output: {
        question_type: DIRECT_SQL | TREND_ANALYTICAL | ALERT_RCA,
        confidence: float,
        classification_reasoning: str,
        rephrased_question: str,
        project_ids: list[str],
        source_tables: list[str],
        focus_area: str,
        causal_explanation: str,   # ALERT_RCA only — exposes graph for UI
        rephrasing_notes: str,
    }
"""
import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
    logger,
)
from app.agents.csod.csod_nodes.narrative import append_csod_narrative
from app.agents.shared.mdl_recommender_schema_scope import refresh_csod_scored_context_schemas
from app.agents.csod.csod_tool_integration import (
    csod_format_scored_context_for_prompt,
    csod_get_tools_for_agent,
)


# ---------------------------------------------------------------------------
# Sub-classifier prompt
# ---------------------------------------------------------------------------

_SUB_CLASSIFIER_SYSTEM_PROMPT = """
### ROLE: CSOD Question Type Classifier ###

You classify a user question into ONE of three types based on its analytical intent:

  DIRECT_SQL       — A concrete lookup, count, or aggregation at a point in time.
                     The answer is a single table or a set of rows/numbers.

  TREND_ANALYTICAL — The question is about change over time, patterns, moving averages,
                     seasonal behaviour, or period-over-period comparison.

  ALERT_RCA        — The question is investigative: why did something happen, what
                     caused a spike/drop, root-cause of an alert or anomaly.

---

### STATIC EXAMPLES ###

DIRECT_SQL:
  - "How many learners completed Security Awareness training in Q3?"
  - "What is the current certification coverage rate for the Finance division?"
  - "List employees with overdue compliance training as of today."
  - "What percentage of assignments were completed within the due date last month?"
  - "Show me the top 10 divisions by training completion count."
  - "What is our overall compliance rate right now?"
  - "How many active learners do we have?"
  - "Give me a breakdown of transcript statuses for mandatory training."

TREND_ANALYTICAL:
  - "How has completion rate changed over the last 6 months by division?"
  - "Is there a seasonal pattern in compliance training lapse rates?"
  - "Compare Q2 vs Q3 certification rates across all business units."
  - "Show me the moving average of assignment completion over the past year."
  - "Which training programs have declining enrollment trends?"
  - "What is the month-over-month trend in overdue training?"
  - "How are completion rates evolving across different cohorts?"
  - "Plot training volume over time for the last two years."

ALERT_RCA:
  - "Why did compliance completion drop 15% last week?"
  - "What caused the spike in overdue training assignments for the Engineering org?"
  - "There's an alert on certification lapse rate — what are the upstream factors?"
  - "Why is the Finance division underperforming vs last quarter on mandatory training?"
  - "What's driving the anomaly in CSOD logins for new hires this month?"
  - "Why did our compliance score drop suddenly?"
  - "An alert fired on overdue certifications — what's the root cause?"
  - "What factors are causing the engagement drop we're seeing?"

---

### BOUNDARY CASE RULES ###

DIRECT_SQL vs TREND_ANALYTICAL:
  "What is the completion rate?" (point-in-time value) → DIRECT_SQL
  "How is the completion rate trending?" (change over time) → TREND_ANALYTICAL
  Signal: does the answer require a time-series or multi-period comparison?
  If yes → TREND_ANALYTICAL. If a single snapshot suffices → DIRECT_SQL.

TREND_ANALYTICAL vs ALERT_RCA:
  "Show me the trend of completions over 6 months" (exploration) → TREND_ANALYTICAL
  "Why did completions suddenly drop last week?" (investigation) → ALERT_RCA
  Signal words for ALERT_RCA: "why", "caused", "spike", "drop", "alert",
  "anomaly", "underperforming", "what happened", "driving factor", "root cause",
  "investigate", "fired" (alert fired).

TRICKY:
  "Why is completion rate low?" → ALERT_RCA (investigative even without explicit trend)
  "How many anomalies were detected?" → DIRECT_SQL (counting, not investigating)
  "What's the trend and why is it declining?" → ALERT_RCA (the why wins)

---

### OUTPUT FORMAT ###
Return ONLY valid JSON (no markdown fences):
{
  "question_type": "DIRECT_SQL" | "TREND_ANALYTICAL" | "ALERT_RCA",
  "confidence": 0.0–1.0,
  "reasoning": "One sentence explaining the classification decision."
}
"""

# ---------------------------------------------------------------------------
# Rephraser prompts (one per type, selected after classification)
# ---------------------------------------------------------------------------

_REPHRASER_DIRECT_SQL_SYSTEM_PROMPT = """
### ROLE: DIRECT_SQL Question Rephraser ###

You receive a user question classified as DIRECT_SQL and a set of available
schemas, tables, columns, and project IDs. Your task:

1. Rephrase the question into ONE precise NL question that:
   - Refers to specific table and column names from the schema context.
   - Includes any necessary filter dimensions (date range, status, org unit).
   - Is unambiguous enough to generate a single SQL query.

2. Identify which project IDs (data models) contain the data needed.
   Use only project IDs that appear in the schema context.

3. List the source tables needed.

4. Identify the focus area (e.g. training_compliance, certification_tracking).

### RULES ###
- Do NOT add analytical operations (trends, moving averages) — this is a direct lookup.
- Do NOT embed causal or time-series language.
- One rephrased question only — do not split into sub-questions.
- project_ids MUST be chosen from the Available project IDs list provided in the input.
- Return EXACTLY 1 project_id if the question can be answered from one data model.
  Return 2 only when a join across two distinct models is strictly necessary.
  Never return more than 2 project_ids.
- Output ONLY valid JSON (no markdown fences).

### OUTPUT FORMAT ###
{
  "rephrased_question": "<precise NL question>",
  "project_ids": ["<project_id_1>"],
  "source_tables": ["<table_name_1>", ...],
  "focus_area": "<focus_area>",
  "causal_explanation": "",
  "rephrasing_notes": "<brief note on what was added/changed and which project_id was chosen>"
}
"""

_REPHRASER_TREND_ANALYTICAL_SYSTEM_PROMPT = """
### ROLE: TREND_ANALYTICAL Question Rephraser ###

You receive a user question classified as TREND_ANALYTICAL and a set of available
schemas, tables, columns, and project IDs. Your task:

1. Rephrase the question into ONE precise NL question that:
   - Specifies the metric being trended (with column names from schema).
   - Specifies time granularity (daily / weekly / monthly) if not given; default to monthly.
   - Specifies the time window if not given; default to last 6 months.
   - Includes any grouping dimensions mentioned or implied (e.g. by division, by org).
   - Is specific enough to drive a time-series SQL or DS function call.

2. Identify which project IDs (data models) contain the relevant time-series data.

3. List the source tables needed (must contain a time column).

4. Identify the focus area.

### RULES ###
- Do NOT embed investigative / root-cause language.
- One rephrased question only.
- Always include a time window and grain in the rephrased question.
- project_ids MUST be chosen from the Available project IDs list provided in the input.
- Return EXACTLY 1 project_id if the time-series data lives in one model.
  Return 2 only when comparing across two distinct data models is strictly necessary.
  Never return more than 2 project_ids.
- Output ONLY valid JSON (no markdown fences).

### OUTPUT FORMAT ###
{
  "rephrased_question": "<precise NL question with metric, grain, and time window>",
  "project_ids": ["<project_id_1>"],
  "source_tables": ["<table_name_1>", ...],
  "focus_area": "<focus_area>",
  "causal_explanation": "",
  "rephrasing_notes": "<brief note on what was added/changed and which project_id was chosen>"
}
"""

_REPHRASER_ALERT_RCA_SYSTEM_PROMPT = """
### ROLE: ALERT_RCA Question Rephraser ###

You receive a user question classified as ALERT_RCA plus causal graph context
(nodes and edges). Your tasks:

1. Rephrase the question into ONE concise NL investigation question that:
   - Names the specific metric/event that triggered the alert or anomaly.
   - Scopes it to the relevant tables/columns from the schema (e.g. "in csod_training_records").
   - Includes the time window of the anomaly if known or inferable.
   - Does NOT embed graph structure, edge names, or node IDs in the question itself.
   - Reads like a natural business question: "What factors contributed to the drop in
     certification completion for the Finance division in the last 2 weeks?"

2. Identify project IDs relevant to the investigation (tables that hold the affected metric
   AND its upstream causal drivers per the causal graph).

3. List source tables.

4. Produce a causal_explanation (separate from the question) that:
   - Shows the relevant portion of the causal graph structure.
   - Identifies the hot paths (root → terminal chains) most relevant to the investigation.
   - Names colliders and confounders that should be controlled.
   - Is written for a human analyst reading the UI (clear sentences + graph references).
   - Format: plain text with sections: "Causal path", "Key drivers", "Confounders to control".

### RULES ###
- The rephrased_question must be graph-structure-free (no "edge X → Y" language).
- causal_explanation should be rich — this is what the UI surfaces to explain the analysis.
- One rephrased question only.
- project_ids MUST be chosen from the Available project IDs list provided in the input.
- Prefer the project_id whose tables contain both the affected metric AND its upstream
  causal drivers. Return EXACTLY 1 project_id if investigation fits in one model.
  Return 2 only when the causal path spans two distinct models.
  Never return more than 2 project_ids.
- Output ONLY valid JSON (no markdown fences).

### OUTPUT FORMAT ###
{
  "rephrased_question": "<concise NL investigation question, graph-structure-free>",
  "project_ids": ["<project_id_1>"],
  "source_tables": ["<table_name_1>", ...],
  "focus_area": "<focus_area>",
  "causal_explanation": "<rich causal path explanation for UI — sections: Causal path | Key drivers | Confounders to control>",
  "rephrasing_notes": "<brief note on what was added/changed and which project_id was chosen>"
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_causal_context_block(state: CSOD_State) -> str:
    """Serialize causal graph context from state for prompt injection."""
    causal_nodes = state.get("csod_causal_nodes", [])
    causal_edges = state.get("csod_causal_edges", [])
    causal_metadata = state.get("csod_causal_graph_metadata", {})
    causal_signals = state.get("causal_signals", {})
    panel_data = state.get("causal_graph_panel_data", {})
    hot_paths = panel_data.get("hot_paths", []) if panel_data else []
    centrality = state.get("csod_causal_centrality") or {}

    if not causal_nodes and not causal_edges:
        return ""

    top_nodes = sorted(
        causal_nodes,
        key=lambda n: (
            0 if n.get("node_type") == "terminal" else
            1 if n.get("node_type") == "root" else 2
        ),
    )[:15]

    top_edges = sorted(
        causal_edges,
        key=lambda e: e.get("confidence_score", 0),
        reverse=True,
    )[:15]

    return f"""
CAUSAL GRAPH CONTEXT:
- Nodes: {len(causal_nodes)}  Edges: {len(causal_edges)}
- Focus area: {causal_signals.get('derived_focus_area', 'N/A')}
- Terminal nodes (outcomes): {causal_metadata.get('terminal_node_ids', [])}
- Collider warnings: {causal_metadata.get('collider_node_ids', [])}
- Confounders: {causal_metadata.get('confounder_node_ids', [])}
- Hot paths: {len(hot_paths)}

Top causal nodes:
{json.dumps([{
    "node_id": n.get("node_id", ""),
    "metric_ref": n.get("metric_ref", ""),
    "node_type": n.get("node_type", ""),
    "is_outcome": n.get("is_outcome", False),
    "collider_warning": n.get("collider_warning", False),
    "description": (n.get("description") or "")[:200],
} for n in top_nodes], indent=2)}

Top causal edges (by confidence):
{json.dumps([{
    "source": e.get("source_node", ""),
    "target": e.get("target_node", ""),
    "direction": e.get("direction", ""),
    "confidence": e.get("confidence_score", 0),
    "lag_days": e.get("lag_window_days", 14),
    "mechanism": (e.get("mechanism") or "")[:150],
} for e in top_edges], indent=2)}

Hot paths (root → terminal):
{json.dumps([{
    "path": hp.get("path", []),
    "confidence": hp.get("path_confidence", 0),
    "lag_total_days": hp.get("lag_total_days", 0),
} for hp in hot_paths[:3]], indent=2)}

Centrality (top 20):
{json.dumps(dict(list(centrality.items())[:20]), indent=2)}
"""


def _pick_rephraser_prompt(question_type: str) -> str:
    if question_type == "DIRECT_SQL":
        return _REPHRASER_DIRECT_SQL_SYSTEM_PROMPT
    if question_type == "TREND_ANALYTICAL":
        return _REPHRASER_TREND_ANALYTICAL_SYSTEM_PROMPT
    return _REPHRASER_ALERT_RCA_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def csod_question_rephraser_node(state: CSOD_State) -> CSOD_State:
    """
    Sub-classify the user question (DIRECT_SQL / TREND_ANALYTICAL / ALERT_RCA),
    rephrase into one precise NL question, and resolve project IDs.

    For ALERT_RCA the rephrased question is graph-structure-free; causal graph
    structure is exposed separately in causal_explanation for the UI.
    """
    user_query = state.get("user_query", "")
    intent = state.get("csod_intent", "")

    try:
        tools: List[Any] = []  # no tool calling needed for this node

        # ── Step 1: Sub-classification ─────────────────────────────────────
        classify_input = f"User question: {user_query}"
        classification_raw = _llm_invoke(
            state, "csod_question_rephraser_classifier",
            _SUB_CLASSIFIER_SYSTEM_PROMPT,
            classify_input,
            tools, False,
        )
        _raw_text = classification_raw.content if hasattr(classification_raw, "content") else str(classification_raw)
        logger.info(
            "[csod_question_rephraser] CLASSIFIER RAW RESPONSE (len=%d):\n%s",
            len(_raw_text), _raw_text[:2000],
        )
        classification = _parse_json_response(classification_raw, {})
        logger.info("[csod_question_rephraser] CLASSIFIER PARSED: %s", classification)
        question_type: str = classification.get("question_type", "DIRECT_SQL")
        if question_type not in ("DIRECT_SQL", "TREND_ANALYTICAL", "ALERT_RCA"):
            question_type = "DIRECT_SQL"
        confidence: float = float(classification.get("confidence", 0.8))
        class_reasoning: str = classification.get("reasoning", "")

        logger.info(
            "[csod_question_rephraser] question_type=%s confidence=%.2f | %s",
            question_type, confidence, class_reasoning,
        )

        # ── Step 2: Schema context ─────────────────────────────────────────
        scored_context = refresh_csod_scored_context_schemas(state)
        schema_str = csod_format_scored_context_for_prompt(
            scored_context,
            include_schemas=True,
            include_metrics=False,
            include_kpis=False,
        )
        logger.info(
            "[csod_question_rephraser] SCHEMA CONTEXT len=%d resolved_project_ids=%s\n"
            "scored_context keys=%s\n"
            "schema_str preview:\n%s",
            len(schema_str),
            state.get("csod_resolved_project_ids"),
            list(scored_context.keys()) if isinstance(scored_context, dict) else type(scored_context).__name__,
            schema_str[:3000] if schema_str else "(empty)",
        )

        # ── Step 3: Causal context (always included, critical for ALERT_RCA) ──
        causal_block = _build_causal_context_block(state)
        logger.info(
            "[csod_question_rephraser] causal_block len=%d has_causal_nodes=%s has_causal_edges=%s",
            len(causal_block),
            bool(state.get("csod_causal_nodes")),
            bool(state.get("csod_causal_edges")),
        )

        # ── Step 4: Rephraser call ─────────────────────────────────────────
        rephraser_system = _pick_rephraser_prompt(question_type)
        resolved_project_ids: List[str] = list(state.get("csod_resolved_project_ids") or [])

        rephraser_input = (
            f"User question: {user_query}\n\n"
            f"Question type (already classified): {question_type}\n\n"
            f"Available project IDs: {json.dumps(resolved_project_ids)}\n\n"
            f"SCHEMA CONTEXT:\n{schema_str}\n"
            + (f"\n{causal_block}" if causal_block else "")
        )
        logger.info(
            "[csod_question_rephraser] REPHRASER INPUT (len=%d) resolved_project_ids=%s",
            len(rephraser_input), resolved_project_ids,
        )

        rephraser_raw = _llm_invoke(
            state, "csod_question_rephraser",
            rephraser_system,
            rephraser_input,
            tools, False,
        )
        _rephraser_raw_text = rephraser_raw.content if hasattr(rephraser_raw, "content") else str(rephraser_raw)
        logger.info(
            "[csod_question_rephraser] REPHRASER RAW RESPONSE (len=%d):\n%s",
            len(_rephraser_raw_text), _rephraser_raw_text[:3000],
        )
        rephraser_result = _parse_json_response(rephraser_raw, {})
        logger.info("[csod_question_rephraser] REPHRASER PARSED RESULT: %s", rephraser_result)

        rephrased_question: str = rephraser_result.get("rephrased_question", user_query)
        raw_project_ids: List[str] = rephraser_result.get("project_ids") or []
        # Clamp to max 2; prefer project IDs that appear in the resolved set
        valid_ids = [p for p in raw_project_ids if p in resolved_project_ids]
        if not valid_ids:
            valid_ids = raw_project_ids  # LLM invented IDs — keep but log
            if raw_project_ids:
                logger.warning(
                    "[csod_question_rephraser] LLM returned project_ids not in resolved set: %s",
                    raw_project_ids,
                )
        output_project_ids: List[str] = valid_ids[:2]
        if not output_project_ids and resolved_project_ids:
            output_project_ids = resolved_project_ids[:1]
        source_tables: List[str] = rephraser_result.get("source_tables", [])
        focus_area: str = rephraser_result.get("focus_area", "")
        causal_explanation: str = rephraser_result.get("causal_explanation", "")
        rephrasing_notes: str = rephraser_result.get("rephrasing_notes", "")

        # ── Step 5: Write output to state ─────────────────────────────────
        output: Dict[str, Any] = {
            "question_type": question_type,
            "confidence": confidence,
            "classification_reasoning": class_reasoning,
            "rephrased_question": rephrased_question,
            "project_ids": output_project_ids,
            "source_tables": source_tables,
            "focus_area": focus_area,
            "causal_explanation": causal_explanation,
            "rephrasing_notes": rephrasing_notes,
        }
        state["csod_question_rephraser_output"] = output
        logger.info(
            "[csod_question_rephraser] FINAL OUTPUT written to state:\n%s",
            json.dumps(output, indent=2, default=str),
        )

        # ── Narrative ─────────────────────────────────────────────────────
        type_label = {
            "DIRECT_SQL": "direct data lookup",
            "TREND_ANALYTICAL": "trend analysis",
            "ALERT_RCA": "alert root-cause investigation",
        }.get(question_type, question_type)
        append_csod_narrative(
            state, "question_rephraser", "Question Rephraser",
            f"Identified as {type_label}. Rephrased for {len(output_project_ids)} project(s).",
            {"question_type": question_type, "project_ids": output_project_ids},
        )

        _csod_log_step(
            state, "csod_question_rephraser", "csod_question_rephraser",
            inputs={"user_query": user_query, "intent": intent},
            outputs={
                "question_type": question_type,
                "confidence": confidence,
                "project_ids": output_project_ids,
                "source_tables": source_tables,
                "has_causal_explanation": bool(causal_explanation),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"Question rephrased | type={question_type} confidence={confidence:.2f} | "
                f"projects={output_project_ids} | "
                f"rephrased: {rephrased_question[:120]}"
            )
        ))

    except Exception as e:
        logger.error("csod_question_rephraser_node failed: %s", e, exc_info=True)
        state["error"] = f"Question rephraser failed: {e}"
        state["csod_question_rephraser_output"] = {
            "question_type": "DIRECT_SQL",
            "confidence": 0.0,
            "classification_reasoning": "",
            "rephrased_question": user_query,
            "project_ids": list(state.get("csod_resolved_project_ids") or []),
            "source_tables": [],
            "focus_area": "",
            "causal_explanation": "",
            "rephrasing_notes": "Fallback — classification failed.",
        }

    return state
