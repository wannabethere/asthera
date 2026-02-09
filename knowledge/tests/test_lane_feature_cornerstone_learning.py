"""
Integration test: full lane feature flow for cornerstone_learning.

Runs the entire flow (Bootstrap -> Silver Features) using LaneFeatureExecutor,
prints the final features, and saves them to JSON. Similar in spirit to
agents/tests/demo_feature_engineering_agent.py but uses the knowledge app's
lane_feature_integration and playbook lanes.

Usage (from repo root or knowledge/):
    python -m tests.test_lane_feature_cornerstone_learning
    python -m tests.test_lane_feature_cornerstone_learning --output-dir /tmp/out
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

# Ensure app is importable
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from langchain_openai import ChatOpenAI

from app.agents.data.retrieval_helper import RetrievalHelper
from app.agents.transform.playbook_driven_transform_agent import LaneDefinition, LaneType
from app.agents.transform.playbook_knowledge_helper import get_playbook_knowledge_helper
from app.assistants.transforms.lane_feature_integration import create_lane_feature_executor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Reduce noise from document storage
logging.getLogger("app.storage.documents").setLevel(logging.WARNING)

PROJECT_ID = "cornerstone_learning"
DOMAIN = "hr_compliance"
COMPLIANCE_FRAMEWORKS = ["SOC2"]

# Lane order: bootstrap (schemas + knowledge) then silver features (final features)
LANE_ORDER = [LaneType.BOOTSTRAP, LaneType.SILVER_FEATURES]


def make_lane_definition(lane_type: LaneType) -> LaneDefinition:
    """Build a minimal LaneDefinition for cornerstone_learning."""
    if lane_type == LaneType.BOOTSTRAP:
        return LaneDefinition(
            lane_id=0,
            lane_type=LaneType.BOOTSTRAP,
            name="Bootstrap",
            description="Load schemas and knowledge for subsequent lanes.",
            agent_name="SchemaAnalysisAgent",
            inputs=[],
            outputs=["enum_metadata"],
            requires_approval=False,
        )
    if lane_type == LaneType.SILVER_FEATURES:
        # Typical learning silver inputs/outputs; retrieval will use project_id for schema
        return LaneDefinition(
            lane_id=5,
            lane_type=LaneType.SILVER_FEATURES,
            name="Silver Features",
            description="Generate silver-layer features for learning and compliance (SOC2).",
            agent_name="FeatureRecommendationAgent",
            inputs=["learning_assignments", "users", "courses"],
            outputs=["silver_features"],
            requires_approval=False,
        )
    # Fallback for any other lane type
    return LaneDefinition(
        lane_id=0,
        lane_type=lane_type,
        name=lane_type.value.replace("_", " ").title(),
        description=f"Lane {lane_type.value} for cornerstone_learning.",
        agent_name="FeatureRecommendationAgent",
        inputs=[],
        outputs=[],
        requires_approval=False,
    )


def initial_playbook_state() -> Dict[str, Any]:
    return {
        "project_id": PROJECT_ID,
        "domain": DOMAIN,
        "compliance_frameworks": COMPLIANCE_FRAMEWORKS,
        "feature_generation_intent": "generic",
        "generate_risk_features": False,
        "schema_context": [],
        "schema_registry": {},
        "silver_features": {},
        "feature_definitions": [],
    }


# KB category ids and display names for SILVER_FEATURES + hr_compliance + SOC2
LANE_CATEGORIES_SILVER_HR_SOC2 = [
    {"id": "cornerstone_silver", "displayName": "Cornerstone Silver", "description": "Learning/training silver-layer features"},
    {"id": "soc2_silver", "displayName": "SOC2 Silver", "description": "SOC2 compliance silver-layer features"},
]


def get_lane_categories(
    lane_type: LaneType,
    domain: str,
    compliance_frameworks: List[str],
) -> List[Dict[str, Any]]:
    """Return KB categories relevant to this lane/domain/frameworks for display and assignment to features."""
    if lane_type != LaneType.SILVER_FEATURES:
        return []
    categories = []
    frameworks_lower = [f.lower() for f in (compliance_frameworks or [])]
    if domain == "hr_compliance":
        categories.append(LANE_CATEGORIES_SILVER_HR_SOC2[0])  # cornerstone_silver
    if "soc2" in frameworks_lower:
        categories.append(LANE_CATEGORIES_SILVER_HR_SOC2[1])  # soc2_silver
    if "hipaa" in frameworks_lower and not any(c["id"] == "hipaa_silver" for c in categories):
        categories.append({"id": "hipaa_silver", "displayName": "HIPAA Silver", "description": "HIPAA compliance silver-layer features"})
    return categories if categories else [{"id": "silver_features", "displayName": "Silver Features", "description": "Silver-layer feature set"}]


def assign_categories_to_features(
    features: List[Dict[str, Any]],
    category_ids: List[str],
) -> List[Dict[str, Any]]:
    """Add a 'categories' list to each feature (in place). Returns the same list."""
    for f in features:
        if isinstance(f, dict):
            f["categories"] = list(category_ids)
    return features


def save_final_features_to_json(
    all_features: List[Dict[str, Any]],
    result_by_lane: Dict[str, Dict[str, Any]],
    playbook_state: Dict[str, Any],
    output_path: Path,
    lane_type_for_categories: LaneType = LaneType.SILVER_FEATURES,
    domain: str = None,
    compliance_frameworks: List[str] = None,
) -> Path:
    """Write final features and metadata to a single JSON file. Adds categories to each feature and a top-level categories list."""
    domain = domain or DOMAIN
    compliance_frameworks = compliance_frameworks or COMPLIANCE_FRAMEWORKS
    lane_categories = get_lane_categories(lane_type_for_categories, domain, compliance_frameworks)
    category_ids = [c["id"] for c in lane_categories]
    assign_categories_to_features(all_features, category_ids)

    silver_result = result_by_lane.get(LaneType.SILVER_FEATURES.value) or {}
    payload = {
        "metadata": {
            "project_id": PROJECT_ID,
            "domain": DOMAIN,
            "compliance_frameworks": COMPLIANCE_FRAMEWORKS,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "lane_order": [lt.value for lt in LANE_ORDER],
        },
        "categories": lane_categories,
        "final_features": all_features,
        "feature_count": len(all_features),
        "calculation_plan": silver_result.get("calculation_plan", {}),
        "dependencies": silver_result.get("dependencies", {}),
        "relevance_scores": silver_result.get("relevance_scores", {}),
        "nl_questions": silver_result.get("nl_questions", []),
        "results_by_lane": {
            lane_type: {
                "success": r.get("success", False),
                "feature_count": len(r.get("features", [])),
                "reasoning": r.get("reasoning", ""),
                "calculation_plan_keys": list(r.get("calculation_plan", {}).keys()),
                "dependencies_keys": list(r.get("dependencies", {}).keys()),
                "nl_questions_count": len(r.get("nl_questions", [])),
            }
            for lane_type, r in result_by_lane.items()
        },
        "playbook_state_summary": {
            "schema_context": playbook_state.get("schema_context", []),
            "schema_registry_tables": list(playbook_state.get("schema_registry", {}).keys()),
            "feature_definitions_count": len(playbook_state.get("feature_definitions", [])),
        },
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return output_path


async def run_full_flow(
    output_dir: Path,
    use_deep_research: bool = True,
    model_name: str = "gpt-4o",
) -> Dict[str, Any]:
    """
    Run Bootstrap + Silver Features for cornerstone_learning and return
    aggregated features plus results per lane.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Dependencies (playbook node uses unprefixed collections, not core_*)
    llm = ChatOpenAI(model=model_name, temperature=0.2)
    retrieval_helper = RetrievalHelper()
    knowledge_helper = get_playbook_knowledge_helper()

    executor = create_lane_feature_executor(
        llm=llm,
        retrieval_helper=retrieval_helper,
        domain_config=None,
        model_name=model_name,
        use_deep_research=use_deep_research,
    )

    playbook_state = initial_playbook_state()
    all_features: List[Dict[str, Any]] = []
    result_by_lane: Dict[str, Dict[str, Any]] = {}

    for lane_type in LANE_ORDER:
        lane_def = make_lane_definition(lane_type)
        knowledge_context = knowledge_helper.get_knowledge_context(
            lane_type=lane_type,
            domain=DOMAIN,
            compliance_frameworks=COMPLIANCE_FRAMEWORKS,
        )

        logger.info("Running lane: %s", lane_type.value)
        result = await executor.execute_lane(
            lane_type=lane_type,
            lane_definition=lane_def,
            playbook_state=playbook_state,
            knowledge_context=knowledge_context,
            user_query=None,
        )

        result_by_lane[lane_type.value] = result

        if not result.get("success"):
            logger.warning("Lane %s failed: %s", lane_type.value, result.get("error"))
            if result.get("awaiting_human_confirmation"):
                # Merge schema state so we can continue
                for k, v in (result.get("state_updates") or {}).items():
                    playbook_state[k] = v
            continue

        # Merge state for next lane
        for k, v in (result.get("state_updates") or {}).items():
            if k == "feature_definitions":
                playbook_state[k] = playbook_state.get(k, []) + (v or [])
            else:
                playbook_state[k] = v

        features = result.get("features") or []
        all_features.extend(features)
        logger.info("Lane %s produced %s features (total so far: %s)", lane_type.value, len(features), len(all_features))

    # Deduplicate by feature_name
    seen = set()
    unique_features = []
    for f in all_features:
        name = (f.get("feature_name") or f.get("name")) if isinstance(f, dict) else None
        if name and name not in seen:
            seen.add(name)
            unique_features.append(f)
        elif not name:
            unique_features.append(f)

    # Save to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"cornerstone_learning_features_{timestamp}.json"
    save_final_features_to_json(
        unique_features,
        result_by_lane,
        playbook_state,
        json_path,
    )
    logger.info("Saved final features to %s", json_path)

    return {
        "success": all(r.get("success") for r in result_by_lane.values()),
        "final_features": unique_features,
        "result_by_lane": result_by_lane,
        "playbook_state": playbook_state,
        "output_path": str(json_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Lane feature integration test for cornerstone_learning")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).parent / "output"),
        help="Directory to write output JSON",
    )
    parser.add_argument(
        "--no-deep-research",
        action="store_true",
        help="Disable deep research context",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="LLM model name",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("Lane Feature Integration Test: cornerstone_learning")
    print("=" * 80)
    print(f"Project: {PROJECT_ID}, Domain: {DOMAIN}, Frameworks: {COMPLIANCE_FRAMEWORKS}")
    print(f"Lanes: {[x.value for x in LANE_ORDER]}")
    print(f"Output dir: {args.output_dir}")
    print("=" * 80)

    result = asyncio.run(
        run_full_flow(
            output_dir=Path(args.output_dir),
            use_deep_research=not args.no_deep_research,
            model_name=args.model,
        )
    )

    features = result.get("final_features") or []
    print(f"\n--- Final features ({len(features)}) ---")
    for i, f in enumerate(features[:20], 1):
        name = (f.get("feature_name") or f.get("name") or "?") if isinstance(f, dict) else "?"
        print(f"  {i}. {name}")
    if len(features) > 20:
        print(f"  ... and {len(features) - 20} more")
    print(f"\nOutput JSON: {result.get('output_path')}")
    print("=" * 80)

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
