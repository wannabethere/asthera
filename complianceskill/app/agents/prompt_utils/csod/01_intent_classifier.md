# Deprecated path — use shared + domain add-on

CSOD intent classification now uses:

1. `prompt_utils/shared/01_analysis_intent_classifier.md` — inject catalog via `<<<INTENT_CATALOG_JSON>>>`
2. `prompt_utils/csod/01_intent_classifier_domain_addon.md` — CSOD taxonomy

Runtime: `app.agents.csod.csod_nodes.node_intent._build_csod_intent_classifier_prompt()`.
