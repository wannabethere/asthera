"""
Transform / Transforms assistant prompts.

All prompts are defined as composable instructions (list of strings) and optional examples (list of dicts).
- Instructions: built from a set of instruction parts; empty list returned if key not found.
- Examples: one or more; empty list returned if key not found.
"""
from typing import Any, Dict, List, Optional

# -----------------------------------------------------------------------------
# Registry: prompt_key -> { "instructions": List[str], "examples": List[dict] }
# Instructions are joined at runtime. Examples are formatted per use.
# -----------------------------------------------------------------------------

TRANSFORM_PROMPT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "identify_feature_buckets_see_understand": {
        "instructions": [
            "You are an expert at mapping HR compliance and learning goals to feature categories.",
            "Perform only the See and Understand steps.",
            "**See** Ingest the context: user goal; selected compliance framework; selected playbook; key concepts from the user's topic selection from source products. Summarize what we have in 1-3 sentences.",
            "**Understand** Map the goal, compliance, playbook, and source topics to feature buckets. Use the external examples to enrich. Which buckets (from the allowed list) apply? Which example ids are relevant?",
            "Allowed feature bucket ids: training_completion, compliance_gap, learning_progress, certification_expiry.",
            'Respond with a JSON object only:\n{"see_summary": "1-3 sentences", "understand_summary": "1-3 sentences", "candidate_buckets": ["id1", "id2"], "relevant_example_ids": ["ex_..."]}\nUse only bucket ids from the allowed list and example ids from the provided external examples.',
        ],
        "examples": [],
    },
    "identify_feature_buckets_decide_act": {
        "instructions": [
            "You are an expert at mapping HR compliance and learning goals to feature categories.",
            "Perform only the Decide and Act steps using the See/Understand output you are given.",
            "**Decide** Reason from the See and Understand summaries. Verdict: which feature buckets apply (true fit), which are marginal, which do not. Surface risk indicators if any (e.g. missing SOC2 coverage). Confirm relevant_example_ids.",
            "**Act** Recommend next steps for the feature plan: how to fetch more details on the chosen buckets and think holistically (e.g. link completion + compliance_gap + certification_expiry for audit readiness).",
            "Allowed feature bucket ids: training_completion, compliance_gap, learning_progress, certification_expiry.",
            'Respond with a JSON object only:\n{"feature_buckets": ["id1", "id2"], "reasoning": "1-2 sentences per phase: See / Understand / Decide / Act.", "relevant_example_ids": ["ex_..."], "next_steps_for_feature_plan": "Brief holistic next steps."}\nUse only bucket ids from the allowed list.',
        ],
        "examples": [],
    },
    "identify_feature_buckets_full": {
        "instructions": [
            "You are an expert at mapping HR compliance and learning goals to feature categories.",
            "Your answer must be associated with: (1) the compliance framework the user selected (e.g. SOC2), (2) the playbook they chose, and (3) the topic selection from the source products (e.g. Workday, Cornerstone). Use this context in See/Understand/Decide/Act.",
            "Use this thinking pattern (See → Understand → Decide → Act) to reason holistically:",
            "**See** Ingest what we have: the user goal; the selected compliance framework (e.g. SOC2); the selected playbook; and key concepts from the user's topic selection from source products (e.g. Workday: headcount, payroll; Cornerstone: learning activity, skills). Treat this as the raw input—machine- or human-generated—that may need investigation.",
            "**Understand** This is where autonomy matters. Extract what matters: map the goal, compliance, playbook, and source topics to feature buckets. Enrich with the external examples provided. Correlate which buckets and examples best support the user's intent for the chosen compliance and playbook. Deduplicate or prioritize without hand-holding.",
            "**Decide** Reason based on the goal, compliance framework, playbook, and examples. Give a verdict: which feature buckets apply (true fit), which are marginal, and which do not. If the system cannot answer the 5Ws for the feature plan from the given context, say so. Surface risk indicators (e.g. missing coverage for SOC2). Recommend which external examples the user should use to fetch more details on each bucket.",
            "**Act** Recommend next steps for the feature plan: how the user can fetch more details on the chosen buckets, and how to think holistically (e.g. link completion + compliance_gap + certification_expiry for audit readiness under the selected compliance). Close the loop so the user can pivot back if needed.",
            "Allowed feature buckets (only use these ids): training_completion, compliance_gap, learning_progress, certification_expiry.\n- training_completion: on-time completion, completion rates, at-risk registrations.\n- compliance_gap: missing required training, coverage gaps, non-compliance counts.\n- learning_progress: progress %, predictive factors, course progress.\n- certification_expiry: expiring certifications, renewal tracking.",
            'Respond with a JSON object:\n{"feature_buckets": ["bucket1", "bucket2"], "reasoning": "1-2 sentences per phase: See / Understand / Decide / Act.", "relevant_example_ids": ["ex_...", "ex_..."], "next_steps_for_feature_plan": "Brief holistic next steps: fetch more details on buckets, how to use examples, and how to close the loop."}\nOnly include bucket ids from the allowed list. Include example ids from the external examples provided when relevant.',
        ],
        "examples": [],
    },
    "structured_graph": {
        "instructions": [
            "You are an expert at structuring HR compliance strategy maps for a UI that displays a graph of sources, entities, features, and metrics.",
            "Given the user's goal, selected feature buckets, and the raw generated features/nl_questions per bucket, produce a single JSON object that defines the graph in the exact format the UI expects. This ensures the output is always structured and the UI can present it reliably.",
            "Output ONLY valid JSON with these top-level keys (no markdown, no explanation):",
            '- sources: array of { "id": "src.<slug>", "label": "Human-readable name" }. Ids must start with "src."',
            '- entities: array of { "id": "ent.<slug>", "label": "Human-readable name" }. One entity per category/bucket. Ids must start with "ent."',
            '- categories: array of { "id": "cat.<bucket_slug>", "label": "Category name", "features": [ { "id": "feat.<slug>", "label": "Feature name", "type": "COUNT|BOOLEAN|FLOAT|STRING|...", "question": "Natural language question", "description": "Short description", "derivedFrom": ["schema.field", ...] } ] }. Feature ids must start with "feat."',
            '- metrics: array of { "id": "met.<slug>", "label": "Metric name", "metricType": "COUNT|RATE|PERCENTAGE|...", "dashboardSection": "Section name", "question": "Natural language question", "description": "Short description", "dependsOnFeatures": ["feat.xxx", ...] }. Metric ids must start with "met."',
            '- edges: array of [ "sourceId", "targetId" ] pairs. Valid connections: source -> entity -> feature -> metric. Use the exact ids from sources, entities, features, and metrics.',
            "Rules: Deduplicate and normalize: one entry per logical source, entity, category, feature, metric. Every feature id in dependsOnFeatures must appear in some category.features[].id. Every edge must reference an id that exists in sources, entities, features, or metrics. Keep labels concise for UI display. Use snake_case for id slugs.",
        ],
        "examples": [],
    },
    "lane_refining_silver": {
        "instructions": [
            "Focus on silver-layer features only. ",
            "Generate per-entity features without population aggregates. ",
        ],
        "examples": [],
    },
    "lane_refining_risk_scoring": {
        "instructions": [
            "Focus on silver-layer features only. ",
            "Generate impact, likelihood, and risk features. ",
            "Use enum metadata tables for classification lookups. ",
        ],
        "examples": [],
    },
    "lane_refining_compliance": {
        "instructions": [
            "Focus on silver-layer features only. ",
            "Generate control evaluation features. ",
            "Include evidence packaging requirements. ",
        ],
        "examples": [],
    },
    "lane_feature_generation_base": {
        "instructions": [
            "Generate features as natural language questions with metadata. ",
            "Include calculation formulas where applicable. ",
            "Specify enum lookups for classifications. ",
        ],
        "examples": [],
    },
}


def get_instructions(prompt_key: str) -> List[str]:
    """Return the list of instruction parts for the prompt key. Empty list if not found."""
    entry = TRANSFORM_PROMPT_REGISTRY.get(prompt_key)
    if not entry:
        return []
    raw = entry.get("instructions")
    if raw is None:
        return []
    return list(raw) if isinstance(raw, (list, tuple)) else [str(raw)]


def get_examples(prompt_key: str) -> List[Dict[str, Any]]:
    """Return the list of examples for the prompt key. Empty list if not found."""
    entry = TRANSFORM_PROMPT_REGISTRY.get(prompt_key)
    if not entry:
        return []
    raw = entry.get("examples")
    if raw is None:
        return []
    return list(raw) if isinstance(raw, (list, tuple)) else []


def build_instructions_text(
    instructions: List[str],
    separator: str = "\n\n",
) -> str:
    """Build a single string from a list of instruction parts. Returns empty string if list is empty."""
    if not instructions:
        return ""
    return separator.join(s for s in instructions if s)


def build_examples_text(
    examples: List[Dict[str, Any]],
    line_format: Optional[str] = None,
) -> str:
    """Format examples for inclusion in a prompt. Returns empty string if list is empty."""
    if not examples:
        return ""
    if line_format is None:
        line_format = "- id: {id} | bucket: {bucket} | {title}\n  {snippet}"
    out = []
    for e in examples:
        try:
            out.append(line_format.format(**e))
        except KeyError:
            out.append(str(e))
    return "\n".join(out)


def get_system_prompt(prompt_key: str, separator: str = "\n\n") -> str:
    """Convenience: get instructions for key and join them. Returns empty string if key not found."""
    instructions = get_instructions(prompt_key)
    return build_instructions_text(instructions, separator=separator)


def append_instructions(
    base_instructions: List[str],
    extra_instructions: List[str],
) -> List[str]:
    """Return a new list: base + extra (composable instruction set)."""
    return list(base_instructions) + list(extra_instructions)


def build_compliance_instructions_blob(compliance_instructions: Optional[Dict[str, Any]], compliance_framework: str) -> str:
    """
    Build a blob of compliance-specific instructions from store format.
    Used to inject into identify_feature_buckets context. Returns empty string if not found.
    """
    if not compliance_instructions or not isinstance(compliance_instructions, dict):
        return ""
    title = compliance_instructions.get("title", "")
    body = compliance_instructions.get("body", "")
    guardrails = compliance_instructions.get("guardrails", [])
    control_mappings = compliance_instructions.get("control_mappings", [])
    examples_inst = compliance_instructions.get("examples", [])
    instructions = [
        f"**Feature processing instructions for {compliance_framework}** ({title}):",
        body,
        "Guardrails: " + "; ".join(guardrails) if guardrails else "",
        "Control mappings: "
        + "; ".join(
            f"{c.get('control_id', '')} ({c.get('name', '')}): {c.get('feature_hint', '')}"
            for c in control_mappings
        )
        if control_mappings else "",
        "Examples: " + "; ".join(examples_inst) if examples_inst else "",
    ]
    return "\n\n".join(s for s in instructions if s)


def get_lane_refining_instructions(lane_type_id: Optional[str], frameworks: Optional[List[str]]) -> str:
    """
    Build refining instructions for lane feature integration.
    lane_type_id: e.g. "silver_features", "risk_scoring", "compliance" (from LaneType.name.lower()).
    Returns base silver if key not found.
    """
    # Map enum-style id to registry key (registry uses short names: silver, risk_scoring, compliance)
    _map = {"silver_features": "silver", "risk_scoring": "risk_scoring", "compliance": "compliance"}
    part = _map.get(lane_type_id, lane_type_id) if lane_type_id else "silver"
    key = f"lane_refining_{part}"
    instructions = get_instructions(key)
    if not instructions:
        instructions = get_instructions("lane_refining_silver")
    text = build_instructions_text(instructions, separator="")
    if frameworks:
        text += f"Target frameworks: {', '.join(frameworks)}. "
    return text


def get_lane_feature_generation_instructions(outputs: Optional[List[str]]) -> str:
    """Build feature generation instructions for lane. outputs = table names to populate."""
    instructions = get_instructions("lane_feature_generation_base")
    text = build_instructions_text(instructions, separator="")
    if outputs:
        text += f"Features should populate these tables: {', '.join(outputs[:3])}. "
    return text
