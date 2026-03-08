"""
Transforms (Agentic Silver) assistant nodes — live under agents/transform so all agents are in one place.

Consumed by app.agents.transform.transforms_module.nodes (re-export) and graph_builder.
"""
import json
import logging
import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.transform.transforms_module.state import TransformsAssistantState
from app.agents.transform.transforms_module.store import (
    AVAILABLE_FEATURE_BUCKETS,
    DEFAULT_COMPLIANCE_FRAMEWORK,
    DEFAULT_SELECTED_SOURCES,
    get_compliance_feature_instructions,
    get_external_examples_for_buckets,
    get_knowledge_context_for_bucket,
    get_lane_definition_for_bucket,
    get_mdl_metrics_by_bucket,
    get_playbook,
    get_source_category,
    list_playbooks_for_goal,
    list_source_categories,
    fetch_data_models_from_vector_store,
)
from app.utils.prompts.transform_prompts import (
    get_system_prompt,
    build_compliance_instructions_blob,
    build_examples_text,
)

logger = logging.getLogger(__name__)


class IntentAndPlaybookNode:
    """
    First step: break down user question into intents, identify playbooks, key concepts per source.
    Currently returns static playbook list and static intents/key concepts (Workday + Cornerstone).
    User then selects playbooks (and sources).
    """

    def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        goal = state.get("goal") or ""
        thinking = (
            "Broken down your goal into intents and matched to available playbooks and sources. "
            "Identified key concepts for each source (Workday, Cornerstone Galaxy). "
            "Select a playbook and source topics to proceed."
        )
        intents = self._intents_from_goal(goal)
        playbooks = list_playbooks_for_goal(goal)
        categories = list_source_categories()
        key_concepts_by_source = {c["id"]: c.get("key_concepts", []) for c in categories}
        out: TransformsAssistantState = {
            "intents": intents,
            "intent_thinking": thinking,
            "key_concepts_by_source": key_concepts_by_source,
            "suggested_playbooks": playbooks,
            "source_categories": categories,
            "agent_thinking": state.get("agent_thinking", []) + [
                {"agent": "intent_and_playbook", "thinking": thinking}
            ],
        }
        return out

    def _intents_from_goal(self, goal: str) -> List[str]:
        """Derive intents from goal. Static for now: compliance + source intents."""
        intents = ["Compliance automation", "Training completion"]
        if goal:
            intents.append("Audit readiness")
        return intents


class PlaybookSuggestionNode:
    """Suggests playbooks based on user goal. Uses dummy store; no silver/gold table names."""

    def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        goal = state.get("goal") or ""
        thinking = (
            "Reviewed your goal and matched it to available compliance playbooks. "
            "Each playbook focuses on continuous compliance and audit readiness without manual effort."
        )
        playbooks = list_playbooks_for_goal(goal)
        out: TransformsAssistantState = {
            "suggested_playbooks": playbooks,
            "playbook_thinking": thinking,
            "agent_thinking": state.get("agent_thinking", []) + [
                {"agent": "playbook_suggestion", "thinking": thinking}
            ],
        }
        return out


class SourceCategoriesNode:
    """Returns source categories (Workday, Cornerstone Galaxy). Dummy agent returning markdown-style content."""

    def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        thinking = (
            "Based on your sources, here are the categories of information available. "
            "Select the topics you need for your audit compliance automation."
        )
        categories = list_source_categories()
        out: TransformsAssistantState = {
            "source_categories": categories,
            "source_categories_thinking": thinking,
            "agent_thinking": state.get("agent_thinking", []) + [
                {"agent": "source_categories", "thinking": thinking}
            ],
        }
        return out


class IdentifyFeatureBucketsNode:
    """
    After user has selected sources: uses LLM to identify feature buckets (categories)
    from config list using See/Understand/Decide/Act thinking (Design_assistance_workforce).
    Prompts and examples come from app.utils.prompts.transform_prompts (instructions + examples).
    """

    def __init__(self, llm: Optional[Any] = None, model_name: str = "gpt-4o-mini"):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)

    async def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        goal = state.get("goal") or ""
        selected_ids = state.get("selected_source_ids") or DEFAULT_SELECTED_SOURCES
        compliance = state.get("selected_compliance_framework") or DEFAULT_COMPLIANCE_FRAMEWORK
        playbook_id = state.get("selected_playbook_id") or ""
        key_concepts_by_source = state.get("key_concepts_by_source") or {}
        selected_concepts: List[str] = []
        for sid in selected_ids:
            selected_concepts.extend(key_concepts_by_source.get(sid, []))
        selected_concepts = list(dict.fromkeys(selected_concepts))

        compliance_instructions = get_compliance_feature_instructions(compliance)
        external_examples = get_external_examples_for_buckets(bucket_ids=None)
        buckets, thinking, next_steps, relevant_ids = await self._identify_buckets(
            goal, selected_concepts, external_examples, compliance, playbook_id, selected_ids, compliance_instructions
        )
        out: TransformsAssistantState = {
            "compliance_feature_instructions": compliance_instructions,
            "feature_buckets": buckets,
            "feature_bucket_thinking": thinking,
            "feature_bucket_next_steps": next_steps or None,
            "relevant_example_ids": relevant_ids or [],
            "agent_thinking": state.get("agent_thinking", []) + [
                {"agent": "identify_feature_buckets", "thinking": thinking}
            ],
        }
        return out

    async def _identify_buckets(
        self,
        goal: str,
        selected_concepts: List[str],
        external_examples: List[dict],
        compliance_framework: str,
        playbook_id: str,
        selected_source_ids: List[str],
        compliance_instructions: Optional[dict],
    ) -> tuple:
        allowed = set(AVAILABLE_FEATURE_BUCKETS)
        examples_blob = build_examples_text(
            external_examples,
            line_format="- id: {id} | bucket: {bucket} | {title}\n  {snippet}",
        )
        instructions_blob = build_compliance_instructions_blob(compliance_instructions, compliance_framework)
        if instructions_blob:
            instructions_blob = instructions_blob + "\n\n"
        context_prompt = (
            "**Context**\n"
            f"Compliance framework: {compliance_framework}\n"
            f"Playbook: {playbook_id or '(none)'}\n"
            f"Source products: {selected_source_ids}\n"
            f"Topic selection (key concepts): {selected_concepts}\n"
            f"User goal: {goal or '(not provided)'}\n\n"
            + (instructions_blob if instructions_blob else "")
            + "**External examples**\n"
            f"{examples_blob}"
        )
        see_understand_system = get_system_prompt("identify_feature_buckets_see_understand")
        decide_act_system = get_system_prompt("identify_feature_buckets_decide_act")
        try:
            # Chain 1: See + Understand
            see_understand_response = await self.llm.ainvoke([
                SystemMessage(content=see_understand_system or "Perform See and Understand steps for feature bucket identification."),
                HumanMessage(content=context_prompt),
            ])
            see_understand_content = see_understand_response.content if hasattr(see_understand_response, "content") else str(see_understand_response)
            chain1_parsed = self._parse_see_understand_response(see_understand_content, allowed, external_examples)

            # Chain 2: Decide + Act (consumes chain 1 output)
            decide_act_prompt = (
                "**See**\n"
                f"{chain1_parsed.get('see_summary', '')}\n\n"
                "**Understand**\n"
                f"{chain1_parsed.get('understand_summary', '')}\n\n"
                f"Candidate buckets: {chain1_parsed.get('candidate_buckets', [])}\n"
                f"Relevant example ids: {chain1_parsed.get('relevant_example_ids', [])}\n\n"
                "Produce the final Decide + Act JSON (feature_buckets, reasoning, relevant_example_ids, next_steps_for_feature_plan)."
            )
            decide_act_response = await self.llm.ainvoke([
                SystemMessage(content=decide_act_system or "Perform Decide and Act steps for feature bucket identification."),
                HumanMessage(content=decide_act_prompt),
            ])
            content = decide_act_response.content if hasattr(decide_act_response, "content") else str(decide_act_response)
            buckets, reasoning, next_steps, relevant_ids = self._parse_buckets_response(
                content, allowed, external_examples
            )
            if not buckets and chain1_parsed.get("candidate_buckets"):
                buckets = [b for b in chain1_parsed["candidate_buckets"] if b in allowed]
            if not relevant_ids and chain1_parsed.get("relevant_example_ids"):
                valid_ids = {e.get("id") for e in external_examples if e.get("id")}
                relevant_ids = [i for i in chain1_parsed["relevant_example_ids"] if i in valid_ids]
            thinking = reasoning or f"Identified feature buckets: {', '.join(buckets)}."
            return buckets, thinking, next_steps, relevant_ids
        except Exception as e:
            logger.warning("IdentifyFeatureBucketsNode LLM failed: %s", e)
            buckets = list(allowed)[:2]
            return (
                buckets,
                f"Fallback buckets (LLM unavailable): {', '.join(buckets)}.",
                None,
                [],
            )

    def _parse_see_understand_response(
        self, content: str, allowed: set, external_examples: List[dict]
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "see_summary": "",
            "understand_summary": "",
            "candidate_buckets": [],
            "relevant_example_ids": [],
        }
        valid_ids = {e.get("id") for e in external_examples if e.get("id")}
        try:
            json_match = re.search(r"\{[\s\S]*\"(?:see_summary|candidate_buckets)\"[\s\S]*\}", content)
            if json_match:
                obj = json.loads(json_match.group(0))
                out["see_summary"] = obj.get("see_summary", "") or ""
                out["understand_summary"] = obj.get("understand_summary", "") or ""
                raw = obj.get("candidate_buckets", [])
                out["candidate_buckets"] = [b for b in raw if isinstance(b, str) and b in allowed]
                raw_ids = obj.get("relevant_example_ids", [])
                out["relevant_example_ids"] = [i for i in raw_ids if isinstance(i, str) and i in valid_ids]
        except (json.JSONDecodeError, KeyError):
            pass
        return out

    def _parse_buckets_response(
        self, content: str, allowed: set, external_examples: List[dict]
    ) -> tuple:
        buckets: List[str] = []
        reasoning = ""
        next_steps: Optional[str] = None
        relevant_ids: List[str] = []
        valid_ids = {e.get("id") for e in external_examples if e.get("id")}
        try:
            json_match = re.search(r"\{[\s\S]*\"feature_buckets\"[\s\S]*\}", content)
            if json_match:
                obj = json.loads(json_match.group(0))
                raw = obj.get("feature_buckets", [])
                buckets = [b for b in raw if isinstance(b, str) and b in allowed]
                reasoning = obj.get("reasoning", "") or ""
                next_steps = obj.get("next_steps_for_feature_plan")
                raw_ids = obj.get("relevant_example_ids", [])
                relevant_ids = [i for i in raw_ids if isinstance(i, str) and i in valid_ids]
            if not buckets:
                for b in allowed:
                    if b in content.lower():
                        buckets.append(b)
                buckets = buckets or list(allowed)[:2]
        except (json.JSONDecodeError, KeyError):
            for b in allowed:
                if b in content.lower():
                    buckets.append(b)
            buckets = buckets or list(allowed)[:2]
        return buckets, reasoning, next_steps, relevant_ids


class FetchDataModelsNode:
    """
    Fetches data models from a vector store relevant to the buckets the user selected
    and to as many sources as selected upfront (workday/cornerstone hardcoded for now).
    Stub uses hardcoded DATA_MODELS_STUB; replace with real vector store search later.
    """

    def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        bucket_ids = state.get("feature_buckets") or []
        source_ids = state.get("selected_source_ids") or DEFAULT_SELECTED_SOURCES
        models = fetch_data_models_from_vector_store(bucket_ids=bucket_ids, source_ids=source_ids)
        thinking = (
            f"Fetched {len(models)} data models from vector store for buckets {bucket_ids} "
            f"and sources {source_ids}. Use these for the feature plan."
        )
        out: TransformsAssistantState = {
            "retrieved_data_models": models,
            "data_models_thinking": thinking,
            "agent_thinking": state.get("agent_thinking", []) + [
                {"agent": "fetch_data_models", "thinking": thinking}
            ],
        }
        return out


class ProcessSelectionQANode:
    """After user selects playbook and source topics, builds a QA response (summary of what can be accomplished)."""

    def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        playbook_id = state.get("selected_playbook_id")
        source_ids = state.get("selected_source_ids") or DEFAULT_SELECTED_SOURCES
        playbook = get_playbook(playbook_id) if playbook_id else None
        sources = [get_source_category(sid) for sid in source_ids]
        sources = [s for s in sources if s is not None]

        if not playbook:
            out: TransformsAssistantState = {
                "qa_response": "No playbook selected. Please choose a playbook and try again.",
                "status": "needs_selection",
            }
            return out

        lines = [
            f"**Selected playbook: {playbook.get('name', playbook_id)}**",
            "",
            playbook.get("summary", playbook.get("description", "")),
            "",
        ]
        compliance_instructions = state.get("compliance_feature_instructions")
        if compliance_instructions:
            lines.append("**Compliance feature processing instructions:**")
            lines.append(compliance_instructions.get("title", "") or "Instructions for selected framework")
            lines.append(compliance_instructions.get("body", "") or "")
            for g in compliance_instructions.get("guardrails", [])[:5]:
                lines.append(f"- {g}")
            lines.append("")
        if sources:
            lines.append("**Selected data sources:**")
            for s in sources:
                lines.append(f"- {s.get('name', s.get('id', ''))}")
            lines.append("")
        feature_buckets = state.get("feature_buckets") or []
        if feature_buckets:
            lines.append("**Feature buckets (categories):**")
            for b in feature_buckets:
                lines.append(f"- {b}")
            lines.append("")
        next_steps = state.get("feature_bucket_next_steps")
        if next_steps:
            lines.append("**Next steps for feature plan:**")
            lines.append(next_steps)
            lines.append("")
        relevant_ids = state.get("relevant_example_ids") or []
        if relevant_ids:
            lines.append("**Relevant examples to fetch more details:**")
            for eid in relevant_ids:
                lines.append(f"- {eid}")
            lines.append("")
        data_models = state.get("retrieved_data_models") or []
        if data_models:
            lines.append("**Data models (from vector store):**")
            for m in data_models:
                name = m.get("name", m.get("model_id", ""))
                source = m.get("source", "")
                snippet = m.get("snippet", "")
                lines.append(f"- [{source}] {name}: {snippet}")
            lines.append("")
        lines.append(
            "You can proceed with this setup for audit compliance automation. "
            "Select buckets and continue to build features, or adjust your selection."
        )
        qa_response = "\n".join(lines)

        out = {
            "qa_response": qa_response,
            "status": "complete",
        }
        return out


def _get_lane_executor():
    """Lazy import to avoid circular deps and heavy agent imports at graph load."""
    from app.agents.transform.transforms_module.lane_feature_integration import (
        LaneType,
        create_lane_feature_executor,
    )
    executor = create_lane_feature_executor(
        model_name="gpt-4o-mini",
        use_deep_research=False,
    )
    return executor, LaneType


class BuildFeaturesNode:
    """
    After user selects continue and buckets: for each selected bucket, calls
    LaneFeatureExecutor (feature_engineering_agent + lane integration) with
    knowledge context from mdl_cornerstone_features.json to generate silver features.
    """

    def __init__(self, lane_executor: Optional[Any] = None):
        self._executor = lane_executor
        self._lane_type = None

    def _get_executor(self):
        if self._executor is not None:
            return self._executor, self._lane_type or _get_lane_executor()[1]
        executor, LaneType = _get_lane_executor()
        self._lane_type = LaneType
        return executor, LaneType

    async def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        bucket_ids = state.get("selected_bucket_ids_for_build") or state.get("feature_buckets") or []
        allowed = set(AVAILABLE_FEATURE_BUCKETS)
        bucket_ids = [b for b in bucket_ids if b in allowed]
        if not bucket_ids:
            return {
                "generated_features_by_bucket": {},
                "build_features_thinking": "No buckets selected for build.",
                "build_status": "skipped",
                "agent_thinking": state.get("agent_thinking", []) + [
                    {"agent": "build_features", "thinking": "No buckets selected for build."}
                ],
            }

        goal = state.get("goal") or ""
        source_ids = state.get("selected_source_ids") or DEFAULT_SELECTED_SOURCES
        compliance = state.get("selected_compliance_framework") or DEFAULT_COMPLIANCE_FRAMEWORK
        retrieved_models = state.get("retrieved_data_models") or []

        executor, LaneType = self._get_executor()
        generated: Dict[str, Any] = {}
        thinking_parts: List[str] = []

        for bucket_id in bucket_ids:
            playbook_state = {
                "domain": "hr_compliance",
                "compliance_frameworks": [compliance],
                "project_id": state.get("session_id") or state.get("thread_id") or "transforms",
                "silver_features": {},
                "feature_generation_intent": "generic",
                "feature_bucket_filter": [bucket_id],
                "generate_risk_features": False,
            }
            try:
                lane_def_dict = get_lane_definition_for_bucket(
                    bucket_id, goal, source_ids, retrieved_models
                )
                lane_definition = SimpleNamespace(**lane_def_dict)
                knowledge_context = get_knowledge_context_for_bucket(bucket_id, [compliance])
                if knowledge_context is None:
                    knowledge_context = get_knowledge_context_for_bucket(bucket_id, None)
                if knowledge_context is None:
                    knowledge_context = SimpleNamespace(
                        features=[], examples=[], instructions=[],
                        enum_metadata=[], compliance_info={}, schema_context=[],
                    )

                result = await executor.execute_lane(
                    lane_type=LaneType.SILVER_FEATURES,
                    lane_definition=lane_definition,
                    playbook_state=playbook_state,
                    knowledge_context=knowledge_context,
                    user_query=goal or f"Generate silver features for {bucket_id}.",
                )
                generated[bucket_id] = result
                if result.get("success"):
                    n = len(result.get("features", []))
                    thinking_parts.append(f"{bucket_id}: generated {n} features.")
                else:
                    thinking_parts.append(f"{bucket_id}: {result.get('error', 'failed')}.")
            except Exception as e:
                logger.warning("BuildFeaturesNode failed for bucket %s: %s", bucket_id, e)
                generated[bucket_id] = {"success": False, "error": str(e), "features": []}
                thinking_parts.append(f"{bucket_id}: error {e!s}.")

        thinking = " ".join(thinking_parts) if thinking_parts else "Build completed."
        success_count = sum(1 for r in generated.values() if r.get("success"))
        build_status = "complete" if success_count == len(bucket_ids) else "partial" if success_count else "failed"

        return {
            "generated_features_by_bucket": generated,
            "build_features_thinking": thinking,
            "build_status": build_status,
            "agent_thinking": state.get("agent_thinking", []) + [
                {"agent": "build_features", "thinking": thinking}
            ],
        }


def _normalize_structured_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all ids have correct prefixes and structure for HRComplianceStrategy."""
    out: Dict[str, Any] = {
        "sources": [],
        "entities": [],
        "categories": [],
        "metrics": [],
        "edges": [],
    }
    for s in (spec.get("sources") or [])[:20]:
        sid = s.get("id", "")
        if not sid.startswith("src."):
            sid = f"src.{sid}" if sid else "src.unknown"
        out["sources"].append({"id": sid, "label": s.get("label", sid)})
    for e in (spec.get("entities") or [])[:20]:
        eid = e.get("id", "")
        if not eid.startswith("ent."):
            eid = f"ent.{eid}" if eid else "ent.unknown"
        out["entities"].append({"id": eid, "label": e.get("label", eid)})
    for c in (spec.get("categories") or [])[:20]:
        feats = []
        for f in (c.get("features") or [])[:50]:
            fid = f.get("id", "")
            if not fid.startswith("feat."):
                fid = f"feat.{fid}" if fid else f"feat.{c.get('id','')}_{len(feats)}"
            feats.append({
                "id": fid,
                "label": f.get("label", fid),
                "type": f.get("type", "unknown"),
                "question": f.get("question", f.get("description", "")),
                "description": f.get("description", f.get("question", "")),
                "derivedFrom": f.get("derivedFrom", []),
            })
        cid = c.get("id", "")
        if not cid.startswith("cat."):
            cid = f"cat.{cid}" if cid else "cat.unknown"
        out["categories"].append({"id": cid, "label": c.get("label", cid), "features": feats})
    for m in (spec.get("metrics") or [])[:30]:
        mid = m.get("id", "")
        if not mid.startswith("met."):
            mid = f"met.{mid}" if mid else f"met.m_{len(out['metrics'])}"
        out["metrics"].append({
            "id": mid,
            "label": m.get("label", mid),
            "metricType": m.get("metricType", "METRIC"),
            "dashboardSection": m.get("dashboardSection", ""),
            "question": m.get("question", m.get("description", "")),
            "description": m.get("description", m.get("question", "")),
            "dependsOnFeatures": m.get("dependsOnFeatures", []),
        })
    seen_edges = set()
    for pair in (spec.get("edges") or [])[:200]:
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            a, b = str(pair[0]), str(pair[1])
            if (a, b) not in seen_edges:
                seen_edges.add((a, b))
                out["edges"].append([a, b])
        elif isinstance(pair, dict) and "source" in pair and "target" in pair:
            a, b = str(pair["source"]), str(pair["target"])
            if (a, b) not in seen_edges:
                seen_edges.add((a, b))
                out["edges"].append([a, b])
    return out


class StructuredGraphNode:
    """
    Asks the LLM to produce a structured graph spec (sources, entities, categories, metrics, edges)
    from the built features so the output is always in the format the UI (HRComplianceStrategy) expects.
    """

    def __init__(self, llm: Optional[Any] = None, model_name: str = "gpt-4o-mini"):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.1)

    async def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        generated = state.get("generated_features_by_bucket") or {}
        goal = state.get("goal") or ""
        buckets = state.get("selected_bucket_ids_for_build") or state.get("feature_buckets") or []
        source_categories = state.get("source_categories") or []
        selected_sources = state.get("selected_source_ids") or DEFAULT_SELECTED_SOURCES

        context_parts = [
            f"User goal: {goal}",
            f"Selected feature buckets: {buckets}",
            f"Selected data sources: {selected_sources}",
        ]
        for c in source_categories:
            if c.get("id") in selected_sources:
                context_parts.append(f"Source: {c.get('id')} - {c.get('name', '')}")
        for bucket_id, result in generated.items():
            if not result.get("success"):
                continue
            context_parts.append(f"\nBucket: {bucket_id}")
            for f in (result.get("features") or [])[:15]:
                name = f.get("feature_name", f.get("name", ""))
                desc = (f.get("description") or f.get("natural_language_question", ""))[:150]
                context_parts.append(f"  - {name}: {desc}")
            for q in (result.get("nl_questions") or [])[:10]:
                context_parts.append(f"  - NL: {q.get('question', q.get('feature_name', ''))[:120]}")
        context = "\n".join(context_parts)
        structured_system = get_system_prompt("structured_graph")
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=structured_system or "Produce a structured JSON graph (sources, entities, categories, metrics, edges)."),
                HumanMessage(content=f"Produce the structured graph JSON for the following context.\n\n{context}"),
            ])
            content = response.content if hasattr(response, "content") else str(response)
            json_match = re.search(r"\{[\s\S]*\"(?:sources|categories)\"[\s\S]*\}", content)
            if json_match:
                spec = json.loads(json_match.group(0))
                normalized = _normalize_structured_spec(spec)
                return {"structured_graph_spec": normalized}
        except Exception as e:
            logger.warning("StructuredGraphNode LLM failed: %s", e)
        return {}


def _build_delivery_outcomes(state: TransformsAssistantState) -> Dict[str, Any]:
    """Build registry-like payload for HRComplianceStrategy / mockRegistry consumption."""
    generated = state.get("generated_features_by_bucket") or {}
    source_categories = state.get("source_categories") or []
    selected_sources = state.get("selected_source_ids") or DEFAULT_SELECTED_SOURCES
    data_models = state.get("retrieved_data_models") or []

    sources = []
    for c in source_categories:
        if c.get("id") in selected_sources:
            sources.append({
                "id": f"src.{c.get('id', '')}",
                "label": c.get("name", c.get("id", "")),
                "icon": "db",
            })
    if not sources and data_models:
        seen = set()
        for m in data_models:
            sid = m.get("source", "")
            if sid and sid not in seen:
                seen.add(sid)
                sources.append({"id": f"src.{sid}", "label": sid.replace("_", " ").title(), "icon": "db"})

    categories = []
    all_feature_ids = []
    metrics = []
    edges_sources_entities = []
    edges_features_metrics = []

    for bucket_id, result in generated.items():
        if not result.get("success"):
            continue
        features = result.get("features", [])
        cat_features = []
        for i, f in enumerate(features):
            fid = f.get("feature_name", f.get("name", f"feat.{bucket_id}_{i}"))
            if not fid.startswith("feat."):
                fid = f"feat.{fid}"
            cat_features.append({
                "id": fid,
                "label": f.get("feature_name", f.get("name", fid)),
                "type": f.get("feature_type", f.get("metric_type", "unknown")),
                "question": f.get("natural_language_question", f.get("description", "")),
                "description": f.get("description", f.get("natural_language_question", "")),
                "derivedFrom": f.get("required_schemas", f.get("schemas", [])),
            })
            all_feature_ids.append(fid)
        if cat_features:
            categories.append({
                "id": f"cat.{bucket_id}",
                "label": bucket_id.replace("_", " ").title(),
                "features": cat_features,
            })

        for q in result.get("nl_questions", [])[:20]:
            name = q.get("feature_name", q.get("question", ""))[:50]
            mid = f"met.{name.replace(' ', '_')}" if name else f"met.{bucket_id}_{len(metrics)}"
            metrics.append({
                "id": mid,
                "label": name or mid,
                "metricType": q.get("feature_type", "METRIC"),
                "dashboardSection": bucket_id.replace("_", " ").title(),
                "question": q.get("question", ""),
                "description": (q.get("question") or "")[:200],
                "dependsOnFeatures": q.get("dependencies", []),
            })
            for dep in q.get("dependencies", []):
                if dep in all_feature_ids or any(dep == cf.get("id") for cat in categories for cf in cat.get("features", [])):
                    edges_features_metrics.append([dep, mid])

    edges = []
    for s in sources:
        for cat in categories:
            edges.append([s["id"], f"ent.{cat['id'].replace('cat.', '')}"])
    for cat in categories:
        for f in cat.get("features", []):
            edges.append([f"ent.{cat['id'].replace('cat.', '')}", f["id"]])
    for a, b in edges_features_metrics:
        edges.append([a, b])

    return {
        "sources": sources,
        "entities": [{"id": f"ent.{c['id'].replace('cat.', '')}", "label": c["label"]} for c in categories],
        "categories": categories,
        "metrics": metrics,
        "edges": edges,
    }


def _build_strategy_graph(delivery_outcomes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build graph in the exact format HRComplianceStrategy.jsx expects:
    - nodes: [{ id, type: "card", position: { x, y }, data: { layer, title, subtitle, badge, description?, derivedFrom? } }]
    - edges: [{ id, source, target, animated: true }]
    Each component describes what's needed for the strategy map (sources, entities, features, metrics).
    """
    X = {"src": 40, "ent": 320, "feat": 620, "met": 950}
    nodes: List[Dict[str, Any]] = []
    edges_out: List[Dict[str, Any]] = []

    sources = delivery_outcomes.get("sources") or []
    entities = delivery_outcomes.get("entities") or []
    categories = delivery_outcomes.get("categories") or []
    metrics = delivery_outcomes.get("metrics") or []
    edge_pairs = delivery_outcomes.get("edges") or []

    for i, s in enumerate(sources):
        nodes.append({
            "id": s.get("id", f"src.{i}"),
            "type": "card",
            "position": {"x": X["src"], "y": 60 + i * 130},
            "data": {
                "layer": "source",
                "title": s.get("label", s.get("id", "")),
                "subtitle": "Source",
                "badge": "SOURCE",
            },
        })

    for i, e in enumerate(entities):
        nodes.append({
            "id": e.get("id", f"ent.{i}"),
            "type": "card",
            "position": {"x": X["ent"], "y": 60 + i * 160},
            "data": {
                "layer": "entity",
                "title": e.get("label", e.get("id", "")),
                "subtitle": "Entity",
                "badge": "ENTITY",
            },
        })

    features_flat: List[Dict[str, Any]] = []
    for cat in categories:
        for f in cat.get("features", []):
            features_flat.append({
                **f,
                "dataType": (f.get("type") or "unknown").upper(),
                "category": cat.get("label", cat.get("id", "")),
            })
    for i, f in enumerate(features_flat):
        nodes.append({
            "id": f.get("id", f"feat.{i}"),
            "type": "card",
            "position": {"x": X["feat"], "y": 40 + i * 90},
            "data": {
                "layer": "feature",
                "title": f.get("label", f.get("id", "")),
                "subtitle": f.get("category", ""),
                "badge": f.get("dataType", "FEATURE"),
                "description": f.get("description", f.get("question", "")),
                "derivedFrom": f.get("derivedFrom", []),
            },
        })

    for i, m in enumerate(metrics):
        metric_type = m.get("metricType", "METRIC")
        dashboard_section = m.get("dashboardSection", "")
        nodes.append({
            "id": m.get("id", f"met.{i}"),
            "type": "card",
            "position": {"x": X["met"], "y": 120 + i * 200},
            "data": {
                "layer": "metric",
                "title": m.get("label", m.get("id", "")),
                "subtitle": f"{metric_type} • {dashboard_section}",
                "badge": metric_type,
                "description": m.get("description", m.get("question", "")),
            },
        })

    for i, pair in enumerate(edge_pairs):
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            edges_out.append({
                "id": f"e-{i}",
                "source": pair[0],
                "target": pair[1],
                "animated": True,
            })
        elif isinstance(pair, dict) and "source" in pair and "target" in pair:
            edges_out.append({
                "id": pair.get("id", f"e-{i}"),
                "source": pair["source"],
                "target": pair["target"],
                "animated": True,
            })

    return {
        "nodes": nodes,
        "edges": edges_out,
    }


def _build_reasoning_plan_steps(state: TransformsAssistantState) -> List[Dict[str, Any]]:
    """Step-by-step reasoning plan from agent_thinking and feature pipeline (reasoning, calculation_plan, generation_reasoning)."""
    steps = []
    for i, t in enumerate(state.get("agent_thinking") or [], 1):
        steps.append({
            "step": i,
            "agent": t.get("agent", ""),
            "summary": t.get("thinking", ""),
        })
    generated = state.get("generated_features_by_bucket") or {}
    base = len(steps)
    for bucket_id, result in generated.items():
        if result.get("reasoning"):
            steps.append({
                "step": base + 1,
                "agent": f"feature_engineering_{bucket_id}",
                "summary": result["reasoning"],
            })
            base += 1
        if result.get("calculation_plan"):
            steps.append({
                "step": base + 1,
                "agent": f"calculation_plan_{bucket_id}",
                "summary": str(result["calculation_plan"])[:500],
            })
            base += 1
        if result.get("generation_reasoning"):
            steps.append({
                "step": base + 1,
                "agent": f"nl_generation_{bucket_id}",
                "summary": result["generation_reasoning"][:500] if isinstance(result["generation_reasoning"], str) else str(result["generation_reasoning"])[:500],
            })
            base += 1
    return steps


def _build_example_sources(state: TransformsAssistantState) -> List[Dict[str, Any]]:
    """Example sources that were provided (external examples + mdl metrics used per bucket)."""
    out = []
    relevant_ids = set(state.get("relevant_example_ids") or [])
    external = get_external_examples_for_buckets(None)
    for e in external:
        if relevant_ids and e.get("id") not in relevant_ids:
            continue
        out.append({
            "id": e.get("id", ""),
            "bucket": e.get("bucket", ""),
            "title": e.get("title", ""),
            "snippet": e.get("snippet", ""),
            "source": e.get("source", "external"),
        })
    bucket_ids = state.get("selected_bucket_ids_for_build") or state.get("feature_buckets") or []
    for bucket_id in bucket_ids:
        for m in get_mdl_metrics_by_bucket(bucket_id):
            out.append({
                "id": m.get("metric_name", m.get("question", ""))[:50],
                "bucket": bucket_id,
                "title": m.get("metric_name", m.get("question", ""))[:80],
                "snippet": m.get("description", m.get("question", ""))[:200],
                "source": "mdl_cornerstone_features",
            })
    return out


class ProcessBuildQANode:
    """After build_features: formats final qa_response, delivery_outcomes, reasoning_plan_steps, and example_sources for frontend (HRComplianceStrategy / mockRegistry)."""

    def __call__(self, state: TransformsAssistantState) -> TransformsAssistantState:
        generated = state.get("generated_features_by_bucket") or {}
        build_status = state.get("build_status") or "unknown"
        thinking = state.get("build_features_thinking") or ""

        lines = [
            "**Feature build complete**",
            "",
            f"Status: {build_status}",
            f"Summary: {thinking}",
            "",
        ]
        for bucket_id, result in generated.items():
            lines.append(f"**Bucket: {bucket_id}**")
            if result.get("success"):
                features = result.get("features", [])
                lines.append(f"Generated {len(features)} features.")
                for f in features[:10]:
                    name = f.get("feature_name", f.get("name", ""))
                    desc = (f.get("description") or f.get("natural_language_question", ""))[:120]
                    lines.append(f"- {name}: {desc}...")
                if len(features) > 10:
                    lines.append(f"- ... and {len(features) - 10} more")
                nl_questions = result.get("nl_questions", [])
                if nl_questions:
                    lines.append("Natural language questions:")
                    for q in nl_questions[:5]:
                        lines.append(f"  - {q.get('question', q.get('feature_name', ''))[:100]}...")
            else:
                lines.append(f"Error: {result.get('error', 'unknown')}")
            lines.append("")

        lines.append("You can use these features in pipelines or refine buckets and rebuild.")
        qa_response = "\n".join(lines)

        structured_spec = state.get("structured_graph_spec")
        if structured_spec and isinstance(structured_spec, dict) and (structured_spec.get("sources") or structured_spec.get("categories") or structured_spec.get("metrics")):
            delivery_outcomes = dict(structured_spec)
        else:
            delivery_outcomes = _build_delivery_outcomes(state)
        strategy_graph = _build_strategy_graph(delivery_outcomes)
        delivery_outcomes["strategy_graph"] = strategy_graph
        reasoning_plan_steps = _build_reasoning_plan_steps(state)
        example_sources = _build_example_sources(state)

        return {
            "qa_response": qa_response,
            "status": "complete",
            "delivery_outcomes": delivery_outcomes,
            "strategy_graph": strategy_graph,
            "reasoning_plan_steps": reasoning_plan_steps,
            "example_sources": example_sources,
        }
