"""
Post–MDL-retrieval enrichment: merge indexed schemas with table_description rows, run
``ContextualDataRetrievalAgent`` (MDL preview stores + project-scoped db_schema /
table_descriptions via RetrievalHelper), then derive relation edges, L1/L2/L3-shaped
artifacts for downstream nodes.

Scope text uses ``mdl_recommender_schema_scope.build_area_scoped_mdl_fallback_query``.
CSOD uses ``MDLRetrievalService(workflow_type="csod")``; DT uses ``workflow_type="dt"``.
No user clarification step — agent and schema index fallbacks carry the flow.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    from app.agents.shared.mdl_recommender_schema_scope import (
        build_area_scoped_mdl_fallback_query as _area_scoped_mdl_query,
    )
except Exception:  # pragma: no cover - import optional in minimal test env

    def _area_scoped_mdl_query(state: Dict[str, Any]) -> str:
        return str(state.get("user_query") or "").strip()


_FK_DDL_RE = re.compile(
    r"FOREIGN\s+KEY\s*\(\s*`?(\w+)`?\s*\)\s*REFERENCES\s*`?([\w.]+)`?\s*\(\s*`?(\w+)`?\s*\)",
    re.IGNORECASE,
)


def _table_key(row: Dict[str, Any]) -> str:
    return str(row.get("table_name") or row.get("name") or "").strip()


def _table_names(schemas: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for s in schemas:
        if not isinstance(s, dict):
            continue
        tn = _table_key(s)
        if tn:
            out.append(tn)
    return out


def extract_mdl_relation_edges(schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse FOREIGN KEY … REFERENCES … from ``table_ddl`` when present.

    Relationship JSON from vector/table_description docs is left on each schema row for
    LLM-facing context; it is not re-normalized here.
    """
    edges: List[Dict[str, Any]] = []
    seen: Set[tuple] = set()
    for s in schemas:
        if not isinstance(s, dict):
            continue
        from_table = str(s.get("table_name") or s.get("name") or "").strip()
        ddl = s.get("table_ddl") or s.get("ddl") or ""
        if from_table and isinstance(ddl, str):
            for m in _FK_DDL_RE.finditer(ddl):
                row = (
                    from_table,
                    m.group(1).lower(),
                    m.group(2).lower(),
                    m.group(3).lower(),
                )
                if row not in seen:
                    seen.add(row)
                    edges.append(
                        {
                            "from_table": from_table,
                            "from_column": m.group(1),
                            "to_table": m.group(2),
                            "to_column": m.group(3),
                        }
                    )
    return edges


def _column_names_from_schema(s: Dict[str, Any]) -> List[str]:
    cols = s.get("column_metadata") or s.get("columns") or []
    out: List[str] = []
    if isinstance(cols, list):
        for c in cols:
            if isinstance(c, dict):
                nm = c.get("column_name") or c.get("name")
                if nm:
                    out.append(str(nm).strip())
            elif c:
                out.append(str(c).strip())
    return [x for x in out if x]


def _schemas_compact_for_relation_inference(
    schemas: List[Dict[str, Any]],
    *,
    max_tables: int = 22,
    max_cols_per_table: int = 40,
) -> str:
    """Minimal table/column text for LLM join inference."""
    rows: List[Dict[str, Any]] = []
    for s in schemas[:max_tables]:
        if not isinstance(s, dict):
            continue
        tn = _table_key(s)
        if not tn:
            continue
        desc = (str(s.get("description") or ""))[:400]
        cols = _column_names_from_schema(s)[:max_cols_per_table]
        rows.append({"table_name": tn, "description": desc, "columns": cols})
    return json.dumps(rows, indent=2)


def _safe_text_for_llm(value: Any) -> str:
    """Normalize text so prompt payload is always JSON-serializable by clients."""
    if value is None:
        return ""
    text = str(value)
    # Remove NULL bytes and invalid/unpaired unicode that can break JSON encoding.
    text = text.replace("\x00", "")
    return text.encode("utf-8", errors="ignore").decode("utf-8")


def _parse_llm_edges_json(content: str) -> List[Dict[str, Any]]:
    text = (content or "").strip()
    if text.startswith("```"):
        first = text.find("```")
        last = text.rfind("```")
        if first >= 0 and last > first:
            text = text[first + 3 : last]
            text = text.replace("json", "", 1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                return []
        else:
            start_o = text.find("{")
            end_o = text.rfind("}") + 1
            if start_o >= 0 and end_o > start_o:
                try:
                    data = json.loads(text[start_o:end_o])
                except json.JSONDecodeError:
                    return []
            else:
                return []
    if isinstance(data, dict) and "edges" in data:
        data = data["edges"]
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _canonical_table_name(name: str, allowed_lower: Dict[str, str]) -> Optional[str]:
    """Map LLM table string to exact name in ``allowed_lower`` keys (lowercase -> canonical)."""
    n = (name or "").strip()
    if not n:
        return None
    return allowed_lower.get(n.lower())


def infer_mdl_relation_edges_llm(
    merged_schemas: List[Dict[str, Any]],
    *,
    context_query: str,
) -> List[Dict[str, Any]]:
    """
    When DDL/metadata produced no edges, ask the LLM for best-effort FK-style links.
    Only emits edges whose endpoints are known table names from ``merged_schemas``.
    """
    allowed = [t for t in _table_names(merged_schemas) if t]
    if len(allowed) < 2:
        return []
    allowed_lower = {t.lower(): t for t in allowed}
    try:
        from langchain_core.prompts import ChatPromptTemplate

        from app.core.dependencies import get_llm
    except Exception as e:
        logger.warning("Relation inference LLM: import failed: %s", e)
        return []

    system = """You infer likely foreign-key-style relationships between database tables for analytics joins.

Output ONE JSON array only (no markdown). Each element:
{{"from_table": "exact name from input", "from_column": "column", "to_table": "exact name from input", "to_column": "column", "confidence": 0.0-1.0}}

Rules:
- Use ONLY table_name values from the input JSON. Match spelling exactly.
- Prefer *_id → id / *_key → key patterns, role names (user_id → users.id), and star-schema facts to dimensions.
- If unsure, omit the edge. At most 40 edges.
- These are best-effort guesses when explicit FK DDL is missing."""

    human = f"""CONTEXT (user / scope):
{_safe_text_for_llm(context_query)[:2500]}

TABLES_JSON (table_name, description, columns):
{_safe_text_for_llm(_schemas_compact_for_relation_inference(merged_schemas))}
"""

    llm = get_llm(temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", "{input}"),
        ]
    )
    chain = prompt | llm
    try:
        resp = chain.invoke({"input": human})
        raw = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        logger.error("Relation inference LLM failed: %s", e, exc_info=True)
        return []

    parsed = _parse_llm_edges_json(raw)
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, str]] = set()
    for e in parsed:
        ft = _canonical_table_name(str(e.get("from_table") or ""), allowed_lower)
        tt = _canonical_table_name(str(e.get("to_table") or ""), allowed_lower)
        fc = str(e.get("from_column") or "").strip()
        tc = str(e.get("to_column") or "").strip()
        if not (ft and tt and fc and tc) or ft == tt:
            continue
        key = (ft.lower(), fc.lower(), tt.lower(), tc.lower())
        if key in seen:
            continue
        seen.add(key)
        row: Dict[str, Any] = {
            "from_table": ft,
            "from_column": fc,
            "to_table": tt,
            "to_column": tc,
            "inferred": True,
            "source": "llm_guess",
        }
        conf = e.get("confidence")
        if isinstance(conf, (int, float)):
            row["confidence"] = float(conf)
        out.append(row)
        if len(out) >= 40:
            break
    return out


def merge_table_description_docs_into_schemas(
    schemas: List[Dict[str, Any]],
    table_descriptions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Enrich schema dicts with description/relationships from table_description index hits."""
    by_name: Dict[str, Dict[str, Any]] = {}
    for td in table_descriptions or []:
        if not isinstance(td, dict):
            continue
        k = _table_key(td)
        if k:
            by_name[k] = td
    out: List[Dict[str, Any]] = []
    for s in schemas:
        if not isinstance(s, dict):
            continue
        copy_s = dict(s)
        tn = _table_key(copy_s)
        extra = by_name.get(tn) if tn else None
        if extra:
            desc = (extra.get("description") or "").strip()
            if desc and not (str(copy_s.get("description") or "").strip()):
                copy_s["description"] = desc
            rels = extra.get("relationships")
            if isinstance(rels, list) and rels and not copy_s.get("relationships"):
                copy_s["relationships"] = rels
        out.append(copy_s)
    return out


def _agent_row_to_schema(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "table_name": row.get("table_name") or "",
        "column_metadata": row.get("column_metadata") or [],
        "table_ddl": row.get("table_ddl") or "",
        "relationships": row.get("relationships") or [],
        "description": row.get("description") or "",
        "score": row.get("score"),
        "score_reason": row.get("score_reason", ""),
    }


def merge_retrieved_schemas_with_contextual_tables(
    existing: List[Dict[str, Any]],
    agent_tables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Union by table_name; prefer richer column_metadata / DDL / description from the agent."""
    by_name: Dict[str, Dict[str, Any]] = {}
    for s in existing:
        if isinstance(s, dict) and _table_key(s):
            by_name[_table_key(s)] = dict(s)
    for t in agent_tables:
        if not isinstance(t, dict):
            continue
        name = (t.get("table_name") or "").strip()
        if not name:
            continue
        new = _agent_row_to_schema(t)
        if name not in by_name:
            by_name[name] = new
        else:
            old = by_name[name]
            if len(new.get("column_metadata") or []) >= len(old.get("column_metadata") or []):
                old["column_metadata"] = new["column_metadata"]
            if (new.get("table_ddl") or "").strip():
                old["table_ddl"] = new["table_ddl"]
            nd = (new.get("description") or "").strip()
            if nd and len(nd) >= len((old.get("description") or "").strip()):
                old["description"] = new["description"]
            if new.get("relationships"):
                old["relationships"] = new["relationships"]
            if new.get("score") is not None:
                old["score"] = new["score"]
            sr = new.get("score_reason")
            if sr:
                old["score_reason"] = sr
    return list(by_name.values())


def build_l3_from_capabilities(required_capability_ids: List[str], table_names: List[str]) -> Dict[str, Dict[str, Any]]:
    default_tbl = table_names[0] if table_names else ""
    out: Dict[str, Dict[str, Any]] = {}
    for cap in sorted({str(x) for x in (required_capability_ids or []) if x}):
        q = cap.replace(".", " ").replace("_", " ")
        out[cap] = {"query_text": q, "filter": {"table": default_tbl}, "n_results": 3}
    return out


def build_l1_from_contextual_agent(discovery: Dict[str, Any], focus_area_categories: List[str]) -> Dict[str, Any]:
    bd = discovery.get("breakdown") or {}
    hints = list(
        dict.fromkeys(
            [str(x) for x in (bd.get("categories") or []) if x]
            + [str(f) for f in focus_area_categories if f]
        )
    )[:30]
    return {
        "focus_alignment": "strong",
        "summary": (discovery.get("summary") or "")[:2000],
        "catalog_focus_hints": hints,
        "user_clarification_prompt": None,
        "source": "contextual_data_retrieval_agent",
        "store_queries": bd.get("store_queries") or [],
    }


def build_l2_from_contextual_agent(
    merged_schemas: List[Dict[str, Any]],
    discovery: Dict[str, Any],
    focus_area_categories: List[str],
) -> Dict[str, Any]:
    breakdown = discovery.get("breakdown") or {}
    cats = list(
        dict.fromkeys(
            [str(x) for x in (breakdown.get("categories") or []) if x]
            + [str(f) for f in focus_area_categories if f]
        )
    )[:20]
    summary = (discovery.get("summary") or "")[:1500]
    scoring = discovery.get("scoring_result") or {}
    scored = {
        s.get("table_name"): s for s in (scoring.get("scored_tables") or []) if isinstance(s, dict) and s.get("table_name")
    }
    l2: Dict[str, Any] = {}
    for s in merged_schemas:
        name = _table_key(s)
        if not name:
            continue
        sc = scored.get(name, {})
        reason = sc.get("reason") if isinstance(sc, dict) else None
        note = (reason or summary or "")[:1200]
        l2[name] = {
            "description": (s.get("description") or "")[:800],
            "grain": "",
            "capability_tags": cats,
            "primary_key": [],
            "foreign_keys": [],
            "filters_required": [],
            "semantic_note": note,
            "contextual_retrieval_score": sc.get("score") if isinstance(sc, dict) else None,
        }
    return l2


def annotate_l2_foreign_keys_from_edges(l2: Dict[str, Any], edges: List[Dict[str, Any]]) -> None:
    """Append human-readable FK lines on L2 rows from relation_edges (deterministic or inferred)."""
    if not isinstance(l2, dict) or not edges:
        return
    for e in edges:
        if not isinstance(e, dict):
            continue
        ft = str(e.get("from_table") or "").strip()
        fc = str(e.get("from_column") or "").strip()
        tt = str(e.get("to_table") or "").strip()
        tc = str(e.get("to_column") or "").strip()
        if not (ft and fc and tt and tc):
            continue
        row = l2.get(ft)
        if not isinstance(row, dict):
            continue
        fks = row.get("foreign_keys")
        if not isinstance(fks, list):
            fks = []
        suffix = " (inferred)" if e.get("inferred") or e.get("source") == "llm_guess" else ""
        line = f"{fc} → {tt}.{tc}{suffix}"
        if line not in fks:
            fks.append(line)
        row["foreign_keys"] = fks


def _resolve_project_id(state: Dict[str, Any]) -> str:
    cp = state.get("compliance_profile") or {}
    return (
        str(state.get("active_project_id") or "").strip()
        or str(cp.get("project_id", "") or "").strip()
        or str(state.get("csod_primary_project_id") or "").strip()
        or str(state.get("project_id") or "").strip()
    )


def enrich_mdl_capability_after_retrieval(
    state: Dict[str, Any],
    *,
    schemas_key: str,
    table_descriptions_key: str,
    l1_key: str,
    l2_key: str,
    l3_key: str,
    relation_key: str,
    needs_clarification_key: str,
    clarification_message_key: str,
    mdl_workflow: str,
) -> None:
    """Populate relation edges and L1/L2/L3 via ContextualDataRetrievalAgent + schema merge."""
    raw = state.get(schemas_key)
    schemas: List[Dict[str, Any]] = raw if isinstance(raw, list) else []

    td_raw = state.get(table_descriptions_key)
    if not isinstance(td_raw, list):
        td_raw = []
    table_descriptions = [x for x in td_raw if isinstance(x, dict)]

    merged_static = merge_table_description_docs_into_schemas(schemas, table_descriptions)

    question = _area_scoped_mdl_query(state).strip()
    if not question:
        question = str(state.get("user_query") or "").strip()
    cap_hints = (state.get("capability_retrieval_hints") or "").strip()
    if cap_hints:
        question = f"{question} {cap_hints}".strip()

    fa = state.get("focus_area_categories") or []
    if not isinstance(fa, list):
        fa = []

    cap = state.get("capability_resolution") or {}
    required = cap.get("required_capability_ids") if isinstance(cap, dict) else []
    if not isinstance(required, list):
        required = []

    project_id = _resolve_project_id(state)

    discovery: Dict[str, Any] = {}
    try:
        from app.agents.mdlworkflows.contextual_data_retrieval_agent import ContextualDataRetrievalAgent
        from app.agents.mdlworkflows.dt_tool_integration import run_async
        from app.retrieval._helper import RetrievalHelper
        from app.retrieval.mdl_service import MDLRetrievalService

        wf = mdl_workflow if mdl_workflow in ("csod", "dt", "leen") else "dt"
        mdl = MDLRetrievalService(workflow_type=wf)
        rh = RetrievalHelper(mdl_service=mdl)
        agent = ContextualDataRetrievalAgent(retrieval_helper=rh, max_tables=15, max_metrics=10)
        discovery = run_async(
            agent.run(
                user_question=question,
                project_id=project_id or None,
                product_name=project_id or None,
                include_table_schemas=bool(project_id),
                include_summary=True,
                session_cache=None,
                focus_area_categories=fa or None,
            )
        )
    except Exception as e:
        logger.warning("MDL contextual enrichment failed, using merged index schemas only: %s", e, exc_info=True)
        discovery = {}

    agent_tables = discovery.get("tables_with_columns") if isinstance(discovery, dict) else []
    if not isinstance(agent_tables, list):
        agent_tables = []

    merged = (
        merge_retrieved_schemas_with_contextual_tables(merged_static, agent_tables)
        if discovery
        else merged_static
    )
    state[schemas_key] = merged

    edges = extract_mdl_relation_edges(merged)
    if not edges and len(_table_names(merged)) >= 2:
        guessed = infer_mdl_relation_edges_llm(merged, context_query=question)
        if guessed:
            edges = guessed
            logger.info(
                "MDL relation edges: DDL/metadata empty; using %s LLM-inferred edge(s)",
                len(guessed),
            )
    state[relation_key] = edges
    allowed = _table_names(merged)
    state[l3_key] = build_l3_from_capabilities(required, allowed)

    if discovery:
        state[l1_key] = build_l1_from_contextual_agent(discovery, fa)
        state[l2_key] = build_l2_from_contextual_agent(merged, discovery, fa)
    else:
        state[l1_key] = {
            "focus_alignment": "strong",
            "summary": "Contextual retrieval unavailable; using merged MDL schema index only.",
            "catalog_focus_hints": fa,
            "user_clarification_prompt": None,
            "source": "schema_index_fallback",
        }
        state[l2_key] = build_l2_from_contextual_agent(
            merged,
            {"summary": "", "breakdown": {}, "scoring_result": {}},
            fa,
        )

    annotate_l2_foreign_keys_from_edges(state[l2_key], edges)

    state[needs_clarification_key] = False
    state[clarification_message_key] = ""


def enrich_csod_mdl_after_retrieval(state: Dict[str, Any]) -> None:
    """Populate CSOD MDL layers using ContextualDataRetrievalAgent (CSOD MDL collections)."""
    enrich_mdl_capability_after_retrieval(
        state,
        schemas_key="csod_resolved_schemas",
        table_descriptions_key="csod_mdl_retrieved_table_descriptions",
        l1_key="csod_mdl_l1_focus_scope",
        l2_key="csod_mdl_l2_capability_tables",
        l3_key="csod_mdl_l3_retrieval_queries",
        relation_key="csod_mdl_relation_edges",
        needs_clarification_key="csod_mdl_needs_focus_clarification",
        clarification_message_key="csod_mdl_focus_clarification_message",
        mdl_workflow="csod",
    )


def enrich_dt_mdl_after_retrieval(state: Dict[str, Any]) -> None:
    """Populate DT MDL layers using ContextualDataRetrievalAgent (default/LEEN collections)."""
    enrich_mdl_capability_after_retrieval(
        state,
        schemas_key="dt_resolved_schemas",
        table_descriptions_key="dt_mdl_retrieved_table_descriptions",
        l1_key="dt_mdl_l1_focus_scope",
        l2_key="dt_mdl_l2_capability_tables",
        l3_key="dt_mdl_l3_retrieval_queries",
        relation_key="dt_mdl_relation_edges",
        needs_clarification_key="dt_mdl_needs_focus_clarification",
        clarification_message_key="dt_mdl_focus_clarification_message",
        mdl_workflow="dt",
    )
