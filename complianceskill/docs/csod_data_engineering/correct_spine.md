Exactly right. The graph topology is what makes the advisory ranking meaningful — `out_degree` tells you which metrics are leading indicators, `node_type` tells you terminal vs mediator vs collider, and the edge structure tells you *which type of analysis* fits the question. Without it, advisory ranking is just keyword matching against focus areas. The split should only happen at the point where you need attribution vs don't.The fork now sits at exactly the right point: after the graph is retrieved, before attribution is computed.

**What the advisory path gains from the concept graph**

For your Cornerstone + Workday example — "which metrics help track course completion rate as a business goal" — the graph retrieval returns a subgraph around `compliance_rate` (terminal) with its connected roots and mediators. The advisory path reads three things from that topology without running CCE or Shapley:

`out_degree` identifies leading indicators. `login_count_weekly_trend` has high out_degree (it influences session_to_user_ratio, completion_rate, cert_compliance_rate). That makes it the right first metric to recommend — it tells you whether the goal is at risk *before* it degrades. Without the graph, you'd have no principled reason to surface it above other engagement metrics.

`node_type = collider` on `completion_rate` surfaces as an advisory note. The user asked about tracking completion rate — the graph immediately shows it's a collider node. The advisory path converts that to plain language: "safe to track as a dashboard KPI, but if it drops don't use it alone to diagnose why — it's driven by both assignment load and engagement simultaneously." That guidance is only possible because the graph was retrieved.

Edge structure suggests the right analysis type. If the retrieved subgraph has a clear terminal node with multiple root paths feeding it, that pattern matches `gap_analysis` or `crown_jewel_analysis`. If the subgraph is mostly a linear chain (A→B→C→terminal), it matches `funnel_analysis`. If the edges have high lag values (21–42 days), it matches `predictive_risk`. The advisory path can surface this as a suggestion: "Based on how these metrics connect, a gap analysis against your 90% target would be the most useful next step" — without computing any attribution.

**What changes in the implementation**

The `vector_causal_graph_node` in `vector_causal_graph_builder.py` runs on both paths unchanged, since it only does retrieval and LLM assembly — no Shapley. The `causal_context_extractor.py` also runs on both paths, since it only reads graph structure (hot paths, centrality, collider flags). What's skipped on the advisory path is everything in `causal_graph_nodes.py` that calls CCE: the lag window scoring, the Shapley coalition construction, and the intervention ordering.

The `advisory_mode` flag in state controls this cleanly:

```python
def causal_context_extractor_node(state):
    # runs on both paths — reads topology only
    context = extract_causal_context(...)
    state["causal_signals"] = context["causal_signals"]
    state["causal_node_index"] = context["causal_node_index"]

    if state.get("advisory_mode"):
        # advisory path: use topology for ranking + analysis type suggestion
        state["dt_advisory_ranking"] = rank_metrics_from_topology(
            context["causal_node_index"],
            state["resolved_metric_candidates"],
        )
        state["suggested_analysis_type"] = infer_analysis_type_from_graph(
            context["causal_graph_panel_data"]
        )
        return state   # stop here — no CCE, no Shapley

    # causal path continues to CCE
    return route_to_cce(state)


def infer_analysis_type_from_graph(panel_data):
    """
    Reads the retrieved graph structure and returns the most probable
    analysis intent — surfaces as a suggestion to the user.
    """
    if not panel_data:
        return None

    hot_paths   = panel_data.get("hot_paths", [])
    terminals   = panel_data.get("terminal_node_ids", [])
    colliders   = panel_data.get("collider_node_ids", [])
    avg_lag     = (
        sum(p["lag_total_days"] for p in hot_paths) / len(hot_paths)
        if hot_paths else 0
    )
    n_terminals = len(terminals)
    n_colliders = len(colliders)

    # Single terminal + long-lag hot paths → gap or predictive
    if n_terminals == 1 and avg_lag > 20:
        return "gap_analysis"          # or compliance_gap_close if deadline_dim present

    # Multiple terminals + branching → crown jewel / advisor
    if n_terminals > 2:
        return "crown_jewel_analysis"

    # Linear chain (short hot paths) → funnel
    if hot_paths and all(len(p["path"]) <= 3 for p in hot_paths):
        return "funnel_analysis"

    # Colliders present + single terminal → gap with collider warning
    if n_colliders > 0 and n_terminals == 1:
        return "gap_analysis"

    return "metrics_dashboard_plan"    # default: safe advisory output
```

**How this changes the output for your Cornerstone + Workday question**

Before (without graph in advisory path), the response would be a ranked list drawn from focus area tags — essentially a filtered list. After, the response looks like:

"Based on how these metrics connect in the LMS graph, here are the most useful metrics for tracking course completion rate as a business goal:

1. `compliance_rate` — this is your terminal KPI (the goal itself). Available from Cornerstone.
2. `login_count_weekly_trend` — leading indicator, 21-day predictive horizon. Available from both CSOD sessions and Workday (sync lag warning — confirm which is fresher).
3. `overdue_count` — primary operational lever, 28-day reachable path to compliance_rate. Cornerstone only.
4. `compliance_assigned_distribution` — root cause signal. Note: full chain takes 42 days — outside a 30-day window.
5. `completion_rate` — safe as a weekly dashboard metric. Note: collider — if it drops, use overdue_count and login_trend together to diagnose the cause, not completion_rate alone.

The graph structure suggests a gap analysis would be most useful next if you have a specific target. Want to run that?"

That last sentence — the analysis type suggestion — is only possible because the graph ran on the advisory path.