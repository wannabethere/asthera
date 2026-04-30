"""
Direct Query Decomposition Planner node.

Runs in Phase 1 after the Cross-Concept Check (CCE) when csod_planner_only=True.
Phase 0 (intent_splitter → mdl_resolver → scoping → area_confirm → metric_narration)
has already run — this node has full scoping + causal context available.

Classifies the user question into one of five planning modes and decomposes it
into atomic questions that the question rephraser can rephrase with schema grounding.

Planning modes:
  single_direct        — one chart/table answers the question
  multi_question       — compound question; split into 2–5 atomic questions
  causal_rca           — alert / root-cause analysis; causal edge retrieval needed
  compare_segments     — side-by-side comparison across dimensions
  explore_recommended  — too broad for Direct mode; user should switch to Explore

State inputs (from Phase 0 + Phase 1 up to CCE):
    user_query, csod_intent
    csod_plan_summary, csod_execution_plan, csod_data_sources_in_scope
    csod_resolved_project_ids, csod_resolved_mdl_table_refs
    csod_scoping_answers, csod_confirmed_concept_ids, compliance_profile
    csod_causal_nodes, csod_causal_edges, csod_causal_graph_metadata

State output:
    csod_direct_query_plan  — full decomposition schema (see OUTPUT_SCHEMA below)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
    logger,
)
from app.agents.csod.csod_tool_integration import csod_format_scored_context_for_prompt
from app.agents.shared.mdl_recommender_schema_scope import refresh_csod_scored_context_schemas

# ---------------------------------------------------------------------------
# LMS table catalog (from design doc — used as fallback hint in prompts)
# ---------------------------------------------------------------------------

_LMS_TABLE_CATALOG = {
    "primary_tables": [
        "transcript_core",
        "training_assignment_core",
        "training_assignment_user_core",
    ],
    "supporting_tables": [
        "users_core",
        "ou_core",
        "user_ou_core",
        "transcript_status_local_core",
        "training_requirement_tag_core",
    ],
    "optional_tables": [
        "assessment_result_core",
        "training_ilt_session_core",
        "training_part_attendance_core",
    ],
}

# ---------------------------------------------------------------------------
# System prompt  (from design doc §5, extended with Phase 0 context injection)
# ---------------------------------------------------------------------------

_DECOMPOSITION_SYSTEM_PROMPT = """
### ROLE: Direct Analysis Query Planner ###

You are the Direct Analysis Query Planner for an LMS compliance analytics agent.

Your job is to inspect the user question — along with the scoping context already
confirmed in conversation (time window, org unit, persona, concept domains, focus
areas) — and decide whether it can be answered as:

  1. single_direct        — one SQL query / one chart answers the whole question.
  2. multi_question       — compound question; split into 2–5 atomic sub-questions.
  3. causal_rca           — alert / root-cause investigation; causal edges needed.
  4. compare_segments     — side-by-side comparison across two or more dimensions.
  5. explore_recommended  — too broad or ambiguous for Direct mode; user should
                            switch to Explore to select metrics interactively.

### INSTRUCTIONS ###

- Do NOT answer the question. Do NOT generate SQL.
- Decompose only when necessary. Prefer 2–5 atomic questions.
- Preserve the user's business intent in every atomic question.
- Use the confirmed scoping context (time window, org unit, persona) to make
  every atomic question concrete and scoped.
- For causal_rca, always include these steps in atomic_questions:
    q1: Validate the observed metric movement.
    q2: Check proximate causal driver(s).
    q3: Check upstream driver(s) of drivers.
    q4: Check confounders (learner count, assignment volume, org size).
    q5: (optional) Segment contribution — which sub-group drives it most?
- For multi_question, each atomic question must have a distinct analysis_type:
    trend_detection | metric_delta | segment_contribution | causal_driver_check |
    confounder_check | alert_validation | recommendation_prioritization |
    compare_segments
- For explore_recommended, set explore_reason to explain why Direct cannot answer.
- For single_direct, atomic_questions must contain exactly one entry.
- For compare_segments, each segment must be a separate atomic question.
- Always populate required_tables from the MDL schemas provided.
  If no schemas are available, use the LMS table catalog below as fallback.
- Set needs_causal_edges=true only for causal_rca or multi_question that needs RCA.
- Set confidence between 0.0 and 1.0.

### LMS TABLE CATALOG (fallback when MDL schemas are unavailable) ###

Primary:   transcript_core, training_assignment_core, training_assignment_user_core
Support:   users_core, ou_core, user_ou_core, transcript_status_local_core,
           training_requirement_tag_core
Optional:  assessment_result_core, training_ilt_session_core,
           training_part_attendance_core

### OUTPUT FORMAT ###

Return ONLY valid JSON (no markdown fences):

{
  "planning_mode": "single_direct | multi_question | causal_rca | compare_segments | explore_recommended",
  "needs_causal_edges": false,
  "needs_multiple_questions": false,
  "direct_answer_allowed": true,
  "explore_recommended": false,
  "explore_reason": "",
  "confidence": 0.0,
  "reasoning": "One sentence explaining the planning decision.",
  "primary_metric_candidates": [],
  "supporting_metric_candidates": [],
  "required_tables": [],
  "atomic_questions": [
    {
      "question_id": "q1",
      "question": "...",
      "analysis_type": "trend_detection | metric_delta | ...",
      "target_metric": "...",
      "tables": ["..."],
      "dimensions": []
    }
  ],
  "causal_focus": {
    "effect_metric": null,
    "candidate_drivers": [],
    "confounders": [],
    "lag_windows_days": []
  },
  "synthesis_instruction": "..."
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_scoping_context_block(state: CSOD_State) -> str:
    """Serialize Phase 0 scoping answers and compliance_profile for prompt injection."""
    parts: List[str] = []

    cp = state.get("compliance_profile") or {}
    if cp.get("time_window"):
        parts.append(f"Time window: {cp['time_window']}")
    if cp.get("org_unit"):
        val = cp.get("org_unit_value") or ""
        parts.append(f"Org unit: {cp['org_unit']}" + (f" ({val})" if val else ""))
    if cp.get("persona"):
        parts.append(f"Persona: {cp['persona']}")
    if cp.get("training_type"):
        parts.append(f"Training type: {cp['training_type']}")

    scoping_answers = state.get("csod_scoping_answers") or {}
    if scoping_answers:
        for k, v in list(scoping_answers.items())[:8]:
            parts.append(f"{k}: {v}")

    confirmed_concepts = state.get("csod_confirmed_concept_ids") or []
    if confirmed_concepts:
        parts.append(f"Confirmed concept domains: {', '.join(str(c) for c in confirmed_concepts)}")

    area_matches = state.get("csod_preliminary_area_matches") or []
    if area_matches:
        area_names = [a.get("area_name") or a.get("name") or "" for a in area_matches[:5]]
        parts.append(f"Preliminary focus areas: {', '.join(a for a in area_names if a)}")

    return "\n".join(parts) if parts else "No scoping context confirmed."


def _build_causal_summary_block(state: CSOD_State) -> str:
    """Brief causal graph summary for the decomp planner prompt."""
    causal_nodes = state.get("csod_causal_nodes") or []
    causal_edges = state.get("csod_causal_edges") or []
    if not causal_nodes and not causal_edges:
        return ""

    metadata = state.get("csod_causal_graph_metadata") or {}
    terminal_ids = metadata.get("terminal_node_ids", [])
    collider_ids = metadata.get("collider_node_ids", [])

    top_nodes = sorted(
        causal_nodes,
        key=lambda n: 0 if n.get("node_type") == "terminal" else 1,
    )[:10]

    top_edges = sorted(
        causal_edges,
        key=lambda e: e.get("confidence_score", 0),
        reverse=True,
    )[:10]

    node_lines = [
        f"  {n.get('node_id','')} ({n.get('node_type','')}) metric={n.get('metric_ref','')}"
        for n in top_nodes
    ]
    edge_lines = [
        f"  {e.get('source_node','')} → {e.get('target_node','')} conf={e.get('confidence_score',0):.2f}"
        f" lag={e.get('lag_window_days',14)}d"
        for e in top_edges
    ]

    return (
        f"\nCAUSAL GRAPH SUMMARY ({len(causal_nodes)} nodes, {len(causal_edges)} edges):\n"
        f"Terminal outcomes: {terminal_ids}\n"
        f"Colliders: {collider_ids}\n"
        f"Top nodes:\n" + "\n".join(node_lines) +
        f"\nTop edges:\n" + "\n".join(edge_lines)
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def csod_direct_query_decomposition_planner_node(state: CSOD_State) -> CSOD_State:
    """
    Classify the user question into a planning mode and decompose it into
    atomic sub-questions, using Phase 0 scoping context + CCE causal graph.

    Writes ``csod_direct_query_plan`` to state.
    """
    user_query: str = state.get("user_query", "")
    intent: str = state.get("csod_intent", "")
    plan_summary: str = state.get("csod_plan_summary") or ""
    data_sources: List[str] = list(state.get("csod_data_sources_in_scope") or [])
    resolved_project_ids: List[str] = list(state.get("csod_resolved_project_ids") or [])

    try:
        # ── Schema context ─────────────────────────────────────────────────
        scored_context = refresh_csod_scored_context_schemas(state)
        schema_str = csod_format_scored_context_for_prompt(
            scored_context,
            include_schemas=True,
            include_metrics=False,
            include_kpis=False,
        )

        # ── Scoping context (Phase 0 output) ───────────────────────────────
        scoping_block = _build_scoping_context_block(state)

        # ── Causal graph summary (CCE output) ──────────────────────────────
        causal_block = _build_causal_summary_block(state)

        # ── Planner context ────────────────────────────────────────────────
        planner_block = ""
        if plan_summary:
            planner_block = f"\nANALYSIS PLAN SUMMARY: {plan_summary}"
        exec_plan = state.get("csod_execution_plan") or []
        if exec_plan:
            step_nls = [
                s.get("semantic_question") or s.get("description", "")
                for s in exec_plan[:4]
                if s.get("semantic_question") or s.get("description")
            ]
            if step_nls:
                planner_block += "\nPLAN STEPS: " + " | ".join(step_nls)

        human_message = (
            f"User question: {user_query}\n\n"
            f"Intent: {intent}\n\n"
            f"Project IDs in scope: {json.dumps(resolved_project_ids)}\n\n"
            f"Data sources: {json.dumps(data_sources)}\n\n"
            f"CONFIRMED SCOPING CONTEXT (from conversation Phase 0):\n{scoping_block}\n"
            + (f"\nMDL SCHEMA CONTEXT:\n{schema_str}\n" if schema_str else "")
            + (causal_block or "")
            + (planner_block or "")
            + "\n\nProduce the decomposition plan JSON."
        )

        logger.info(
            "[csod_direct_query_decomp_planner] input_len=%d intent=%s project_ids=%s",
            len(human_message), intent, resolved_project_ids,
        )

        raw = _llm_invoke(
            state,
            "csod_direct_query_decomp_planner",
            _DECOMPOSITION_SYSTEM_PROMPT,
            human_message,
            [],
            False,
        )
        plan: Dict[str, Any] = _parse_json_response(raw, {})

        # Ensure required keys exist with safe defaults
        plan.setdefault("planning_mode", "single_direct")
        plan.setdefault("needs_causal_edges", False)
        plan.setdefault("needs_multiple_questions", False)
        plan.setdefault("direct_answer_allowed", True)
        plan.setdefault("explore_recommended", plan.get("planning_mode") == "explore_recommended")
        plan.setdefault("explore_reason", "")
        plan.setdefault("confidence", 0.8)
        plan.setdefault("reasoning", "")
        plan.setdefault("atomic_questions", [])
        plan.setdefault("primary_metric_candidates", [])
        plan.setdefault("supporting_metric_candidates", [])
        plan.setdefault("required_tables", [])
        plan.setdefault("causal_focus", {
            "effect_metric": None,
            "candidate_drivers": [],
            "confounders": [],
            "lag_windows_days": [],
        })
        plan.setdefault("synthesis_instruction", "")

        # If LLM produced no atomic_questions, create one from the user query
        if not plan["atomic_questions"]:
            plan["atomic_questions"] = [{
                "question_id": "q1",
                "question": user_query,
                "analysis_type": "trend_detection"
                if intent in ("adhoc_analysis",) else "metric_delta",
                "target_metric": "",
                "tables": data_sources[:3] or _LMS_TABLE_CATALOG["primary_tables"],
                "dimensions": [],
            }]

        state["csod_direct_query_plan"] = plan

        logger.info(
            "[csod_direct_query_decomp_planner] planning_mode=%s atomic_questions=%d "
            "needs_causal=%s explore=%s confidence=%.2f",
            plan["planning_mode"],
            len(plan["atomic_questions"]),
            plan["needs_causal_edges"],
            plan["explore_recommended"],
            plan["confidence"],
        )

        _csod_log_step(
            state,
            "csod_direct_query_decomp_planner",
            "csod_direct_query_decomp_planner",
            inputs={"user_query": user_query, "intent": intent},
            outputs={
                "planning_mode": plan["planning_mode"],
                "atomic_questions": len(plan["atomic_questions"]),
                "explore_recommended": plan["explore_recommended"],
                "confidence": plan["confidence"],
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"Direct query plan: mode={plan['planning_mode']} "
                f"questions={len(plan['atomic_questions'])} "
                f"explore={plan['explore_recommended']}"
            )
        ))

    except Exception as exc:
        logger.error(
            "[csod_direct_query_decomp_planner] failed: %s", exc, exc_info=True
        )
        state["csod_direct_query_plan"] = {
            "planning_mode": "single_direct",
            "needs_causal_edges": False,
            "needs_multiple_questions": False,
            "direct_answer_allowed": True,
            "explore_recommended": False,
            "explore_reason": "",
            "confidence": 0.0,
            "reasoning": f"Decomposition failed: {exc}",
            "atomic_questions": [{
                "question_id": "q1",
                "question": user_query,
                "analysis_type": "metric_delta",
                "target_metric": "",
                "tables": [],
                "dimensions": [],
            }],
            "primary_metric_candidates": [],
            "supporting_metric_candidates": [],
            "required_tables": [],
            "causal_focus": {
                "effect_metric": None,
                "candidate_drivers": [],
                "confounders": [],
                "lag_windows_days": [],
            },
            "synthesis_instruction": "",
        }

    return state
