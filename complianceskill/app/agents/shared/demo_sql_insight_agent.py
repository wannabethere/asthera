"""
Demo-only synthetic SQL + insights (no LLM calls).

Builds plausible gold-model SQL, tabular preview rows, and data-science-style insights
from CSOD/conversation state so the output assembler can show end-to-end UI without
warehouse connectivity.

Enable with settings DEMO_FAKE_SQL_AND_INSIGHTS=true (env: DEMO_FAKE_SQL_AND_INSIGHTS).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_DEMO_AGENT_ID = "demo_sql_insight_synthesizer_v1"


def _as_str_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x.strip() else []
    if isinstance(x, Sequence) and not isinstance(x, (str, bytes, dict)):
        return [str(i) for i in x if i is not None and str(i).strip()]
    return []


def _concept_labels(concepts: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(concepts, list):
        return out
    for c in concepts:
        if not isinstance(c, dict):
            continue
        label = (
            c.get("title")
            or c.get("name")
            or c.get("concept_name")
            or c.get("label")
            or c.get("id")
        )
        if label:
            out.append(str(label))
    return out


def _focus_area_labels(state: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    cp = state.get("compliance_profile")
    if isinstance(cp, dict):
        for fa in cp.get("resolved_focus_areas") or []:
            if isinstance(fa, dict):
                n = fa.get("name") or fa.get("id") or fa.get("focus_area_id")
                if n:
                    labels.append(str(n))
    for fa in state.get("resolved_focus_areas") or []:
        if isinstance(fa, dict):
            n = fa.get("name") or fa.get("id") or fa.get("focus_area_id")
            if n and n not in labels:
                labels.append(str(n))
    de = state.get("data_enrichment")
    if isinstance(de, dict):
        for x in de.get("suggested_focus_areas") or []:
            if x and str(x) not in labels:
                labels.append(str(x))
    pa = state.get("csod_primary_area")
    if isinstance(pa, dict):
        n = pa.get("area_name") or pa.get("name") or pa.get("id")
        if n and str(n) not in labels:
            labels.append(str(n))
    return labels


def _primary_metric_record(state: Dict[str, Any]) -> Dict[str, Any]:
    rm = state.get("resolved_metrics") or []
    if isinstance(rm, list) and rm and isinstance(rm[0], dict):
        return rm[0]
    recs = state.get("csod_metric_recommendations") or []
    if isinstance(recs, list) and recs and isinstance(recs[0], dict):
        return recs[0]
    dt_recs = state.get("dt_metric_recommendations") or []
    if isinstance(dt_recs, list) and dt_recs and isinstance(dt_recs[0], dict):
        return dt_recs[0]
    return {}


def _causal_snippets(state: Dict[str, Any]) -> List[str]:
    snippets: List[str] = []

    def _walk_paths(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("from_concept", "to_concept", "cause", "effect", "node", "label"):
                    if isinstance(v, str) and v.strip():
                        snippets.append(v.strip())
                _walk_paths(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk_paths(item)

    pa = state.get("csod_primary_area")
    if isinstance(pa, dict):
        _walk_paths(pa.get("causal_paths") or [])

    for m in state.get("csod_area_matches") or []:
        if isinstance(m, dict):
            _walk_paths(m.get("causal_paths") or [])

    cg = state.get("csod_causal_graph") or state.get("causal_graph_context")
    if isinstance(cg, dict):
        for key in ("nodes", "edges", "paths"):
            _walk_paths(cg.get(key) or [])
    elif isinstance(cg, list):
        _walk_paths(cg)

    # de-dupe preserving order
    seen: set[str] = set()
    uniq: List[str] = []
    for s in snippets:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:12]


def collect_demo_sql_agent_context(
    state: Dict[str, Any],
    metric_override: Optional[Dict[str, Any]] = None,
    *,
    workflow: str = "csod",
) -> Dict[str, Any]:
    """
    Inputs a real LLM SQL agent would use: projects, focus areas, concepts,
    metric NL question + metadata, and causal-graph-related labels.
    """
    pids = list(
        dict.fromkeys(
            _as_str_list(state.get("csod_resolved_project_ids"))
            + _as_str_list(state.get("csod_primary_project_id"))
            + _as_str_list(state.get("active_project_id"))
        )
    )
    concepts = _concept_labels(
        state.get("csod_selected_concepts") or state.get("csod_concept_matches")
    )
    focus = _focus_area_labels(state)
    base_m = _primary_metric_record(state)
    if isinstance(metric_override, dict) and metric_override:
        metric = {**base_m, **metric_override}
    else:
        metric = base_m
    nl_q = (
        metric.get("natural_language_question")
        or metric.get("question")
        or state.get("user_query")
        or ""
    )
    causal = _causal_snippets(state)

    return {
        "project_ids": pids,
        "focus_area_labels": focus,
        "concept_labels": concepts,
        "metric_id": metric.get("metric_id") or metric.get("id") or "demo_metric",
        "metric_name": metric.get("name") or "Demo metric",
        "metric_description": metric.get("description") or "",
        "natural_language_question": str(nl_q).strip() or "Demo analytics question",
        "metric_context": {
            "category": metric.get("category"),
            "kpis": metric.get("kpis"),
            "trends": metric.get("trends"),
            "source_schemas": metric.get("source_schemas"),
            "data_capability": metric.get("data_capability"),
        },
        "causal_graph_concepts": causal,
        "user_query": state.get("user_query") or "",
        "datasource": state.get("csod_selected_datasource"),
        "workflow": workflow,
    }


def _sql_slug(parts: Sequence[str]) -> str:
    raw = "_".join(p for p in parts if p) or "demo"
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", raw.lower()).strip("_")
    return (slug[:48] or "demo_metric") if slug else "demo_metric"


def _stable_seed(ctx: Dict[str, Any]) -> int:
    payload = json.dumps(
        {
            "p": ctx.get("project_ids"),
            "m": ctx.get("metric_id"),
            "q": ctx.get("natural_language_question"),
        },
        sort_keys=True,
    )
    h = hashlib.sha256(payload.encode())
    return int.from_bytes(h.digest()[:4], "big")


def _fake_rows(seed: int) -> Tuple[List[str], List[Dict[str, Any]]]:
    cols = [
        "period",
        "project_id",
        "metric_value",
        "cohort_size",
        "yoy_delta_pct",
    ]
    rows: List[Dict[str, Any]] = []
    base = (seed % 900) + 100
    for i in range(5):
        rows.append(
            {
                "period": f"2025-0{4 + i}-01",
                "project_id": f"proj_{(seed + i) % 7 + 1:02d}",
                "metric_value": round(base * (1.02 + 0.01 * i), 2),
                "cohort_size": 1200 + i * 37,
                "yoy_delta_pct": round(1.5 + (seed % 5) * 0.4 + i * 0.2, 2),
            }
        )
    return cols, rows


def synthesize_demo_outputs(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Return gold SQL entries, insights, result sets, and artifact name."""
    seed = _stable_seed(ctx)
    slug = _sql_slug(
        [
            str(ctx.get("metric_id") or ""),
            ctx.get("metric_name") or "",
        ]
    )
    project_filter = (
        ", ".join(f"'{p}'" for p in (ctx.get("project_ids") or [])[:5])
        or "'demo_project'"
    )
    concepts_sql = ", ".join(
        f"'{c[:40].replace(chr(39), chr(39)+chr(39))}'"
        for c in (ctx.get("concept_labels") or [])[:6]
    ) or "'general_lms'"

    focus_sql = ", ".join(
        f"'{f[:40].replace(chr(39), chr(39)+chr(39))}'"
        for f in (ctx.get("focus_area_labels") or [])[:6]
    ) or "'learning_effectiveness'"

    causal_comment = ""
    if ctx.get("causal_graph_concepts"):
        causal_comment = (
            "\n  /* Causal context: "
            + ", ".join(ctx["causal_graph_concepts"][:6])
            + " */\n"
        )

    silver_ref = (
        "silver_siem_normalized_events"
        if ctx.get("workflow") == "dt"
        else "silver_lms_learning_events"
    )
    sql = f"""-- Demo gold model (synthetic) — {_DEMO_AGENT_ID}
-- Question: {ctx.get('natural_language_question', '')[:200]}
{causal_comment}WITH scoped AS (
  SELECT *
  FROM {{ ref('{silver_ref}') }}
  WHERE connection_id = '{{{{ var(\"connection_id\") }}}}'
    AND project_id IN ({project_filter})
    AND focus_area IN ({focus_sql})
    AND concept_bucket IN ({concepts_sql})
)
SELECT
  date_trunc('month', event_at) AS period,
  project_id,
  COUNT(*) AS metric_value,
  COUNT(DISTINCT user_id) AS cohort_size,
  0.12 AS confidence_score
FROM scoped
GROUP BY 1, 2
"""

    gold_name = f"gold_demo_{slug}"
    gold_entry = {
        "name": gold_name,
        "sql_query": sql,
        "description": (
            f"Synthetic demo gold model for {ctx.get('metric_name')} "
            f"({ctx.get('metric_id')})"
        ),
        "materialization": "table",
        "expected_columns": [
            {"name": "period", "description": "Month bucket"},
            {"name": "project_id", "description": "Resolved project scope"},
            {"name": "metric_value", "description": "Aggregated event count"},
            {"name": "cohort_size", "description": "Distinct learners"},
            {"name": "confidence_score", "description": "Demo placeholder"},
        ],
    }

    cols, rows = _fake_rows(seed)
    result_sets = [
        {
            "label": f"Preview: {ctx.get('metric_name')}",
            "source": _DEMO_AGENT_ID,
            "columns": cols,
            "rows": rows,
        }
    ]

    insight_nl = ctx.get("natural_language_question") or ""
    insights = [
        {
            "insight_id": f"demo_ins_{slug[:20]}",
            "insight_name": f"Demo insight — {ctx.get('metric_name')}",
            "insight_type": "trend_summary",
            "sql_function": "COUNT + DISTINCT over scoped learning events",
            "target_metric_id": ctx.get("metric_id"),
            "target_table_name": gold_name,
            "description": (
                f"Synthetic insight for demo: projects {ctx.get('project_ids')}, "
                f"focus {ctx.get('focus_area_labels')[:3]}, "
                f"concepts {ctx.get('concept_labels')[:3]}. "
                f"Question: {insight_nl[:160]}"
            ),
            "parameters": {
                "demo": True,
                "causal_graph_concepts": ctx.get("causal_graph_concepts") or [],
                "metric_context": ctx.get("metric_context") or {},
            },
            "business_value": (
                "Illustrative only — enable DEMO_FAKE_SQL_AND_INSIGHTS for UI demos."
            ),
        }
    ]

    return {
        "gold_models": [gold_entry],
        "artifact_name": f"demo_gold_{slug}",
        "data_science_insights": insights,
        "result_sets": result_sets,
        "context_snapshot": ctx,
    }


def apply_demo_sql_insight_agent_to_state(state: Dict[str, Any]) -> bool:
    """
    Populate state with synthetic SQL + insights. Returns True if mutations applied.

    Idempotent: if ``csod_generated_gold_model_sql`` is already non-empty, skips.
    """
    existing = state.get("csod_generated_gold_model_sql") or []
    if existing:
        return False

    ctx = collect_demo_sql_agent_context(state, workflow="csod")
    out = synthesize_demo_outputs(ctx)

    state["csod_demo_sql_agent_context"] = out["context_snapshot"]
    state["csod_demo_sql_result_sets"] = out["result_sets"]
    state["csod_demo_sql_insights_synthetic"] = True
    state["csod_generated_gold_model_sql"] = out["gold_models"]
    state["csod_gold_model_artifact_name"] = out["artifact_name"]

    prior = state.get("csod_data_science_insights") or []
    if not isinstance(prior, list):
        prior = []
    demo_insights = out["data_science_insights"]
    merged = prior + [i for i in demo_insights if isinstance(i, dict)]
    state["csod_data_science_insights"] = merged

    logger.info(
        "%s: synthesized gold model %s + %s insight(s)",
        _DEMO_AGENT_ID,
        out["gold_models"][0]["name"] if out["gold_models"] else "?",
        len(demo_insights),
    )
    return True


def _recommended_metrics_for_workflow(state: Dict[str, Any], workflow: str) -> List[Dict[str, Any]]:
    raw: List[Any] = []
    if workflow == "dt":
        raw = list(state.get("dt_metric_recommendations") or [])
    else:
        raw = list(state.get("csod_metric_recommendations") or [])
        if not raw:
            rm = state.get("resolved_metrics") or []
            if isinstance(rm, list):
                raw = rm
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for m in raw:
        if not isinstance(m, dict):
            continue
        mid = str(
            m.get("metric_id") or m.get("id") or m.get("name") or len(seen)
        )
        if mid in seen:
            continue
        seen.add(mid)
        out.append(m)
    return out


def apply_demo_sql_insight_agent_to_dt_state(state: Dict[str, Any]) -> bool:
    """Like CSOD demo agent but fills dt_* gold SQL + dt_data_science_insights."""
    existing = state.get("dt_generated_gold_model_sql") or []
    if existing:
        return False

    ctx = collect_demo_sql_agent_context(state, workflow="dt")
    out = synthesize_demo_outputs(ctx)

    state["dt_demo_sql_agent_context"] = out["context_snapshot"]
    state["dt_demo_sql_result_sets"] = out["result_sets"]
    state["dt_demo_sql_insights_synthetic"] = True
    state["dt_generated_gold_model_sql"] = out["gold_models"]
    state["dt_gold_model_artifact_name"] = out["artifact_name"]

    prior = state.get("dt_data_science_insights") or []
    if not isinstance(prior, list):
        prior = []
    demo_insights = out["data_science_insights"]
    state["dt_data_science_insights"] = prior + [
        i for i in demo_insights if isinstance(i, dict)
    ]

    logger.info(
        "%s (dt): synthesized %s",
        _DEMO_AGENT_ID,
        out["gold_models"][0]["name"] if out["gold_models"] else "?",
    )
    return True


def apply_per_metric_demo_sql_insights(
    state: Dict[str, Any],
    workflow: str,
) -> List[str]:
    """
    When DEMO_FAKE_SQL_AND_INSIGHTS is on, append one synthetic gold model + insight
    per recommended metric (cap DEMO_PER_METRIC_SQL_INSIGHTS_MAX).
    """
    from app.core.settings import get_settings

    if not get_settings().DEMO_FAKE_SQL_AND_INSIGHTS:
        return []

    metrics = _recommended_metrics_for_workflow(state, workflow)
    cap = max(1, int(get_settings().DEMO_PER_METRIC_SQL_INSIGHTS_MAX))
    metrics = metrics[:cap]
    if not metrics:
        return []

    wf = "dt" if workflow == "dt" else "csod"
    gold_key = "dt_generated_gold_model_sql" if wf == "dt" else "csod_generated_gold_model_sql"
    insight_key = "dt_data_science_insights" if wf == "dt" else "csod_data_science_insights"
    preview_key = "dt_demo_sql_result_sets" if wf == "dt" else "csod_demo_sql_result_sets"

    gold_list: List[Dict[str, Any]] = list(state.get(gold_key) or [])
    ins_list: List[Dict[str, Any]] = list(state.get(insight_key) or [])
    if not isinstance(ins_list, list):
        ins_list = []
    previews: List[Dict[str, Any]] = list(state.get(preview_key) or [])
    per_metric: List[Dict[str, Any]] = list(
        state.get("shared_per_metric_demo_artifacts") or []
    )

    for m in metrics:
        ctx = collect_demo_sql_agent_context(state, metric_override=m, workflow=wf)
        out = synthesize_demo_outputs(ctx)
        gm = out.get("gold_models") or []
        if gm and isinstance(gm[0], dict):
            gold_list.append(gm[0])
        for ins in out.get("data_science_insights") or []:
            if isinstance(ins, dict):
                ins_list.append(ins)
        for rs in out.get("result_sets") or []:
            if isinstance(rs, dict):
                previews.append(rs)
        per_metric.append(
            {
                "metric_id": ctx.get("metric_id"),
                "metric_name": ctx.get("metric_name"),
                "gold_model_name": (gm[0].get("name") if gm else None),
                "preview_columns": (out.get("result_sets") or [{}])[0].get("columns")
                if out.get("result_sets")
                else [],
            }
        )

    state[gold_key] = gold_list
    state[insight_key] = ins_list
    state[preview_key] = previews
    state["shared_per_metric_demo_artifacts"] = per_metric
    return ["per_metric_demo_sql_insights"]


def apply_per_metric_stub_artifacts(
    state: Dict[str, Any],
    workflow: str,
) -> List[str]:
    """
    Without demo mode: still attach one lightweight row per recommended metric so
    assemblers can reference metrics consistently.
    """
    from app.core.settings import get_settings

    if get_settings().DEMO_FAKE_SQL_AND_INSIGHTS:
        return []

    metrics = _recommended_metrics_for_workflow(state, workflow)
    if not metrics:
        return []

    stubs = []
    for m in metrics[
        : max(1, int(get_settings().DEMO_PER_METRIC_SQL_INSIGHTS_MAX))
    ]:
        mid = m.get("metric_id") or m.get("id") or m.get("name")
        stubs.append(
            {
                "metric_id": mid,
                "metric_name": m.get("name"),
                "artifact_stub": True,
                "note": "Link metric to aggregate gold_model_sql / playbook sections",
            }
        )
    state["shared_per_metric_artifact_stubs"] = stubs
    return ["per_metric_artifact_stubs"]
