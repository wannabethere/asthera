"""
Attribution & intervention ordering — design reference.

Canonical implementation (stubs + dispatch + upgrade markers):
  app.agents.causalgraph.cce_attribution

Import from there:
  run_attribution, choose_attribution_method,
  llm_attribution_and_ordering, shapley_on_observations,
  prepare_cce_attribution_context, build_stub_metric_current_values,
  merge_attribution_into_causal_graph_result, ATTRIBUTION_RESULT_KEYS

Response shape (always): method, method_detail, contributions, intervention_order,
blocked_metrics, diagnosis, confidence, is_placeholder.

Upgrade: Phase 2 = replace body of llm_attribution_and_ordering only.
         Phase 3 = replace body of shapley_on_observations only.
         Wire metric_current_values and metric_observations on state before live phases.
"""
