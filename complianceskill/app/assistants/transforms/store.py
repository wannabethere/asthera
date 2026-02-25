"""
Dummy store for playbooks and source categories (Agentic Silver workflow).

Playbooks: compliance-oriented templates; descriptions only, no silver/gold table names.
Source categories: placeholder by source (e.g. Workday, Cornerstone Galaxy).
MDL cornerstone features: load from data/cornerstoneanalytics/mdl_cornerstone_features.json
for knowledge context and lane definitions per feature bucket.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from app.agents.transform.playbook_knowledge_helper import KnowledgeContext
except ImportError:
    KnowledgeContext = None

# Dummy playbook store — one entry for demo (HR Compliance Manager)
PLAYBOOK_STORE: List[dict] = [
    {
        "id": "hr_compliance_manager",
        "name": "HR Compliance Manager",
        "description": "This ensures we always know our training compliance status, can fix issues early, and are audit-ready at all times without manual effort.",
        "summary": (
            "Stay continuously compliant with required training: see who is assigned what, "
            "who has completed on time, and where gaps exist. Get early visibility into issues, "
            "focus outreach where it matters, and answer auditor questions with clear evidence "
            "and traceability—without scrambling at audit time."
        ),
    },
]

# Dummy source categories with key concepts (from AgenticSilverWorkflowInstructions)
SOURCE_CATEGORIES_STORE: List[dict] = [
    {
        "id": "workday",
        "name": "Workday",
        "description_md": """Workday provides authoritative data for:

- Headcount, hiring, and attrition
- Payroll, compensation, and cost structures
- Organizational hierarchies and job architecture

It answers: Who is in the workforce, where they sit, and what they cost.""",
        "key_concepts": [
            "Headcount, hiring, and attrition",
            "Payroll, compensation, and cost structures",
            "Organizational hierarchies and job architecture",
        ],
    },
    {
        "id": "cornerstone_galaxy",
        "name": "Cornerstone Galaxy – The System of Talent Intelligence",
        "description_md": """Cornerstone Galaxy provides:

- Learning activity and outcomes
- Skills acquisition and proficiency
- Performance, readiness, and potential
- Talent mobility and development signals""",
        "key_concepts": [
            "Learning activity and outcomes",
            "Skills acquisition and proficiency",
            "Performance, readiness, and potential",
            "Talent mobility and development signals",
        ],
    },
]

# Defaults for graph invoke when not provided (hardcode for now).
DEFAULT_SELECTED_SOURCES: List[str] = ["workday", "cornerstone_galaxy"]
DEFAULT_COMPLIANCE_FRAMEWORK: str = "SOC2"

# Instructions for processing features per compliance framework. Hardcoded for now; will be fetched (e.g. vector store) later.
SOC2_FEATURE_PROCESSING_INSTRUCTIONS: dict = {
    "framework": "SOC2",
    "title": "SOC2 feature processing instructions",
    "guardrails": [
        "Silver-layer only: per-entity features; no gold aggregations in feature definitions.",
        "Per-asset / per-person derived fields only; no org-wide completion rates or portfolio rollups in silver.",
        "Control evidence must map to specific trust criteria (e.g. CC6.1, CC7.2) where applicable.",
    ],
    "control_mappings": [
        {"control_id": "CC6.1", "name": "Logical and Physical Access Controls", "feature_hint": "Access, identity, and assignment evidence."},
        {"control_id": "CC7.2", "name": "System Monitoring", "feature_hint": "Monitoring coverage, freshness, and agent/telemetry evidence."},
        {"control_id": "CC8.1", "name": "Change Management", "feature_hint": "Version, change, and approval signals."},
    ],
    "examples": [
        "Training completion: on-time completion rate per person/OU; at-risk registrations; due-date vs completion evidence for audit.",
        "Compliance gap: count of employees missing required training; obligation-to-assignment coverage; in-scope population vs assigned.",
        "Certification expiry: certifications expiring within N days; renewal tracking by department/OU for SOC2 evidence.",
    ],
    "body": (
        "When processing features for SOC2, align to trust service criteria and common points of focus. "
        "Produce row-level (silver) evidence that supports control evaluation; avoid aggregate KPIs in the feature layer. "
        "Link features to control IDs where possible for audit readiness."
    ),
}

COMPLIANCE_FRAMEWORK_FEATURE_INSTRUCTIONS: dict = {
    "SOC2": SOC2_FEATURE_PROCESSING_INSTRUCTIONS,
}


def get_compliance_feature_instructions(framework: str) -> Optional[dict]:
    """Return feature-processing instructions for the given compliance framework. Hardcoded for now; fetch from vector store later."""
    return COMPLIANCE_FRAMEWORK_FEATURE_INSTRUCTIONS.get(framework.upper() if framework else "")


# Available feature buckets (categories) from mdl_cornerstone_features.json feature_patterns.
# Used by IdentifyFeatureBucketsNode to map goal + selected source key concepts -> buckets.
AVAILABLE_FEATURE_BUCKETS: List[str] = [
    "training_completion",
    "compliance_gap",
    "learning_progress",
    "certification_expiry",
]

# External examples to help the user fetch more details on buckets and think holistically
# for the feature plan. Hardcoded for now; will be filled from vector store search later.
EXTERNAL_EXAMPLES_FOR_BUCKETS: List[dict] = [
    {
        "id": "ex_training_completion_1",
        "bucket": "training_completion",
        "title": "On-time completion rates by department",
        "snippet": "Track completion rates and at-risk registrations by OU/department; use for audit evidence and early intervention.",
        "source": "cornerstone_playbook",
    },
    {
        "id": "ex_compliance_gap_1",
        "bucket": "compliance_gap",
        "title": "Coverage gaps and missing required training",
        "snippet": "Identify employees missing required training or certifications; map obligations to assignments for coverage gap analysis.",
        "source": "cornerstone_playbook",
    },
    {
        "id": "ex_learning_progress_1",
        "bucket": "learning_progress",
        "title": "Learning progress and predictive factors",
        "snippet": "Average progress by course type; predictive factors for on-time completion; use for readiness and talent mobility.",
        "source": "cornerstone_playbook",
    },
    {
        "id": "ex_certification_expiry_1",
        "bucket": "certification_expiry",
        "title": "Certifications expiring soon",
        "snippet": "Count certifications expiring within a window; aggregate by department/OU for renewal tracking and compliance.",
        "source": "cornerstone_playbook",
    },
]


def get_external_examples_for_buckets(bucket_ids: Optional[List[str]] = None) -> List[dict]:
    """Return external examples (for prompt / vector store later). If bucket_ids given, filter by bucket."""
    if not bucket_ids:
        return [e.copy() for e in EXTERNAL_EXAMPLES_FOR_BUCKETS]
    return [e.copy() for e in EXTERNAL_EXAMPLES_FOR_BUCKETS if e.get("bucket") in bucket_ids]


# Hardcoded data models per bucket/source; replace with vector store search later.
DATA_MODELS_STUB: List[dict] = [
    {"source": "workday", "bucket": "training_completion", "model_id": "workday.assignments", "name": "Assignments", "snippet": "Workday assignment and due-date model for training obligations."},
    {"source": "workday", "bucket": "compliance_gap", "model_id": "workday.obligations", "name": "Obligations", "snippet": "Obligation and role-based requirement model for coverage gap."},
    {"source": "cornerstone_galaxy", "bucket": "training_completion", "model_id": "csod.training_instances", "name": "Training instances", "snippet": "Cornerstone training instances and completion status (silver)."},
    {"source": "cornerstone_galaxy", "bucket": "compliance_gap", "model_id": "csod.training_obligations", "name": "Training obligations", "snippet": "Obligation catalog and assignment coverage for compliance gap."},
    {"source": "cornerstone_galaxy", "bucket": "learning_progress", "model_id": "csod.learning_progress", "name": "Learning progress", "snippet": "Progress and predictive factors for on-time completion."},
    {"source": "cornerstone_galaxy", "bucket": "certification_expiry", "model_id": "csod.certifications", "name": "Certifications", "snippet": "Certification and expiry model for renewal tracking."},
]


def fetch_data_models_from_vector_store(
    bucket_ids: List[str],
    source_ids: List[str],
) -> List[dict]:
    """
    Fetch data models relevant to the selected buckets and sources.
    Hardcoded stub for now; replace with real vector store search later.
    """
    if not bucket_ids:
        bucket_ids = list(AVAILABLE_FEATURE_BUCKETS)
    if not source_ids:
        source_ids = list(DEFAULT_SELECTED_SOURCES)
    out = [
        m.copy()
        for m in DATA_MODELS_STUB
        if m.get("bucket") in bucket_ids and m.get("source") in source_ids
    ]
    return out


def list_playbooks_for_goal(goal: str) -> list:
    """Return playbooks relevant to the user goal. Dummy: returns all (one) for demo."""
    return [p.copy() for p in PLAYBOOK_STORE]


def list_source_categories() -> list:
    """Return available source categories. Dummy: returns Workday + Cornerstone."""
    return [s.copy() for s in SOURCE_CATEGORIES_STORE]


def get_playbook(playbook_id: str) -> Optional[dict]:
    """Get a single playbook by id."""
    for p in PLAYBOOK_STORE:
        if p["id"] == playbook_id:
            return p.copy()
    return None


def get_source_category(source_id: str) -> Optional[dict]:
    """Get a single source category by id."""
    for s in SOURCE_CATEGORIES_STORE:
        if s["id"] == source_id:
            return s.copy()
    return None


# ---------------------------------------------------------------------------
# MDL cornerstone features (from data/cornerstoneanalytics/mdl_cornerstone_features.json)
# ---------------------------------------------------------------------------

def _get_mdl_path() -> Optional[Path]:
    """Resolve path to mdl_cornerstone_features.json (flowharmonicai/data/cornerstoneanalytics)."""
    try:
        base = Path(__file__).resolve().parent
        for _ in range(5):
            base = base.parent
        path = base / "data" / "cornerstoneanalytics" / "mdl_cornerstone_features.json"
        return path if path.exists() else None
    except Exception:
        return None


def load_mdl_cornerstone_features() -> Dict[str, Any]:
    """Load mdl_cornerstone_features.json; return dict with name, version, metrics, sourceSchemas, etc. Empty dict if not found."""
    path = _get_mdl_path()
    if not path or not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def get_mdl_metrics_by_bucket(bucket_id: str) -> List[Dict[str, Any]]:
    """Return metrics from mdl_cornerstone_features where feature_patterns contains bucket_id."""
    mdl = load_mdl_cornerstone_features()
    metrics = mdl.get("metrics", [])
    return [m for m in metrics if isinstance(m, dict) and bucket_id in (m.get("feature_patterns") or [])]


def get_knowledge_context_for_bucket(
    bucket_id: str,
    compliance_frameworks: Optional[List[str]] = None,
) -> Any:
    """
    Build KnowledgeContext for a feature bucket using mdl_cornerstone_features metrics.
    Used by BuildFeaturesNode to feed LaneFeatureExecutor with examples in the same shape as mdl.
    """
    if KnowledgeContext is None:
        return None
    metrics = get_mdl_metrics_by_bucket(bucket_id)
    frameworks = compliance_frameworks or [DEFAULT_COMPLIANCE_FRAMEWORK]
    features = []
    examples = []
    for m in metrics:
        name = m.get("metric_name", m.get("question", ""))
        desc = m.get("description", m.get("question", ""))
        features.append({
            "name": name,
            "feature_name": name,
            "description": desc,
            "natural_language_question": m.get("question", desc),
            "feature_type": m.get("metric_type", "unknown"),
            "required_entities": m.get("required_entities", []),
            "aggregation_levels": m.get("aggregation_levels", []),
            "schemas": m.get("schemas", []),
        })
        examples.append({
            "question": m.get("question", ""),
            "metric_name": name,
            "description": desc,
            "feature_patterns": m.get("feature_patterns", []),
            "schemas": m.get("schemas", []),
        })
    return KnowledgeContext(
        features=features,
        examples=examples,
        instructions=[],
        enum_metadata=[],
        compliance_info={"frameworks": frameworks},
        schema_context=[],
    )


def get_lane_definition_for_bucket(
    bucket_id: str,
    goal: str,
    source_ids: List[str],
    retrieved_data_models: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build a minimal lane definition for LaneFeatureExecutor (SILVER_FEATURES).
    Must have: name, description, inputs, outputs; lane_type is set by caller.
    """
    inputs = []
    if retrieved_data_models:
        for m in retrieved_data_models:
            if m.get("bucket") == bucket_id:
                model_id = m.get("model_id", m.get("name", ""))
                if model_id:
                    inputs.append(model_id)
    if not inputs:
        mdl = load_mdl_cornerstone_features()
        schemas = mdl.get("sourceSchemas", [])
        if not schemas and mdl.get("metrics"):
            seen = set()
            for met in mdl.get("metrics", []):
                for s in (met.get("schemas") or []):
                    if s and s not in seen:
                        seen.add(s)
                        inputs.append(s)
            if not inputs:
                inputs = ["training_instances", "employee", "course"]
        else:
            inputs = list(schemas)[:10]
    return {
        "name": f"silver_features_{bucket_id}",
        "description": f"Generate silver-layer features for {bucket_id}. {goal or 'Compliance and audit readiness.'}",
        "inputs": inputs[:15],
        "outputs": ["silver_features"],
        "lane_type": "silver_features",
    }
