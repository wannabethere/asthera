# Lexy Conversational Flow — Implementation Plan v2
## Concept-Driven Context Selection + Registry-Backed Pipeline Wiring

**Changes from v1:** This revision adds a **Phase 0 — Context Setup** layer before any conversational phases. The user selects a datasource and picks concepts they care about. These selections drive all downstream decisions: which `project_ids` are activated, which recommendation areas are surfaced, and how the CSOD pipeline state is pre-populated. The vector store holds both registries; no LLM classification is needed for concept selection.

---

## 1. Revised Conversation Arc

```
Phase 0 — Context Setup    (NEW)
  Step A: User selects datasource (Cornerstone, Snyk, Workday, etc.)
  Step B: Lexy presents available concepts for that datasource
  Step C: User selects 1–3 concepts they care about
          → project_ids resolved from source_concept_registry
          → recommendation_areas preloaded from concept_recommendation_registry

Phase 1 — Intent Confirm
  Lexy identifies the specific question intent
  Presents relevant recommendation_areas as choices (NOT raw metric names)
  User picks which area(s) to focus on

Phase 2 — Scoping
  2–3 targeted questions: org unit, time window, context-specific filters
  (filter options come from concept_recommendation_registry[area_id].filters)

Phase 3 — Metric Build Narration
  Lexy explains WHAT it will measure and WHY
  Narration is generated from recommendation_area.causal_paths + metrics

Phase 4 — Dashboard  (CSOD pipeline output, unchanged)
```

---

## 2. Registry Role Clarification

### `source_concept_registry.json`
**Role:** Datasource → concept catalogue + project resolution

```
source_concept_map[datasource][concept_id] → {
    project_ids: [...],          ← used to set active_project_id / selected_project_ids
    mdl_table_refs: [...],       ← passed into schema retrieval filter
    coverage_confidence: 0.85    ← shown as data availability signal in UI
}
```

**key_concepts** (the 10 concept objects) supply the display text for Phase 0 Step B:
- `concept_id`, `display_name`, `description`, `trigger_keywords`, `business_questions`

### `concept_recommendation_registry.json`
**Role:** Concept → recommendation areas (the sub-categories surfaced in Phase 1)

```
concept_recommendations[concept_id].recommendation_areas[n] → {
    area_id, display_name, description,
    metrics: [...],              ← resolved into csod_retrieved_metrics filter
    kpis: [...],                 ← passed to scoring validator as priority KPIs
    filters: [...],              ← drive Phase 2 scoping question selection
    causal_paths: [...],         ← used in Phase 3 metric narration
    natural_language_questions,  ← used as intent confirmation examples in Phase 1
    data_requirements: [...]     ← tables passed to mdl_schema_retrieval
}
```

---

## 3. Updated Data Models — `conversation_state.py`

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ConversationPhase(str, Enum):
    # Phase 0 (NEW)
    DATASOURCE_SELECT = "datasource_select"      # Step A: pick datasource
    CONCEPT_SELECT = "concept_select"            # Step B+C: pick concepts
    # Phase 1
    INTENT_CONFIRM = "intent_confirm"            # Confirm use-case + area
    # Phase 2
    SCOPING = "scoping"
    # Phase 3
    METRIC_BUILD = "metric_build"
    # Terminal
    CONFIRMED = "confirmed"
    PIPELINE_RUNNING = "pipeline_running"
    DASHBOARD = "dashboard"


class LexyFlow(str, Enum):
    COMPLIANCE_RISK = "compliance_training"          # maps to concept_id
    LEARNING_EFFECTIVENESS = "learning_effectiveness"
    TRAINING_ROI = "training_roi"
    WORKFORCE_CAPABILITY = "workforce_capability"
    LMS_HEALTH = "lms_health"
    CERTIFICATION_TRACKING = "certification_tracking"
    TRAINING_COMPLETION = "training_completion"
    KNOWLEDGE_RETENTION = "knowledge_retention"
    METRIC_ADVISOR = "metric_kpi_advisor"
    UNKNOWN = "unknown"


class ScopingAnswers(BaseModel):
    org_unit: Optional[str] = None
    org_unit_value: Optional[str] = None
    time_window: Optional[str] = None
    training_type: Optional[str] = None
    onset_pattern: Optional[str] = None
    breadth: Optional[str] = None
    persona: Optional[str] = None
    cost_focus: Optional[str] = None
    skills_domain: Optional[str] = None
    # NEW: dynamic filter values from recommendation area
    additional_filters: Dict[str, Any] = Field(default_factory=dict)


class SelectedConcept(BaseModel):
    concept_id: str
    display_name: str
    project_ids: List[str]
    mdl_table_refs: List[str]
    coverage_confidence: float
    recommendation_areas: List[Dict[str, Any]]    # from concept_recommendation_registry


class ConversationState(BaseModel):
    session_id: str
    user_query: str = ""
    phase: ConversationPhase = ConversationPhase.DATASOURCE_SELECT
    flow: LexyFlow = LexyFlow.UNKNOWN

    # Phase 0 — Context
    datasource: Optional[str] = None                           # "cornerstone" | "snyk" | "workday"
    available_concepts: List[Dict[str, Any]] = Field(default_factory=list)   # from key_concepts filtered by datasource
    selected_concepts: List[SelectedConcept] = Field(default_factory=list)   # user-picked

    # Phase 1 — Selected recommendation area(s)
    selected_area_ids: List[str] = Field(default_factory=list)
    active_recommendation_areas: List[Dict[str, Any]] = Field(default_factory=list)

    # Phase 2 — Scoping
    scoping: ScopingAnswers = Field(default_factory=ScopingAnswers)
    pending_scoping_questions: List[Dict] = Field(default_factory=list)

    # Phase 3 — Metric narration
    metric_narration: Optional[str] = None

    # Resolved project context
    active_project_id: Optional[str] = None       # primary (first match)
    selected_project_ids: List[str] = Field(default_factory=list)   # all matched
    selected_data_sources: List[str] = Field(default_factory=list)
    active_mdl_tables: List[str] = Field(default_factory=list)      # union of mdl_table_refs

    # Pipeline wiring
    csod_intent: Optional[str] = None
    causal_graph_enabled: bool = True
    use_advisor_workflow: bool = False

    messages: List[Dict[str, str]] = Field(default_factory=list)
```

---

## 4. Registry Loader — `registry_loader.py`

This module loads and indexes both JSON registries at startup. In production these are fetched from the vector store; this file provides the in-process index for fast lookup.

```python
"""
Registry loader for source_concept_registry and concept_recommendation_registry.
Loaded once at startup; used by Phase 0 orchestrator and ProjectContextBuilder.

In production:
  - Both JSONs are indexed in ChromaDB / vector store
  - concept_lookup() does a semantic search over key_concepts.description + trigger_keywords
  - area_lookup() does a semantic search over recommendation_areas.description + natural_language_questions
  - The sync dict-based lookups below are used as fast fallback / offline mode
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# ── Load registries ──────────────────────────────────────────────────────────
# Update paths to match your project structure
_REGISTRY_DIR = Path("data/registries")

def _load(filename: str) -> dict:
    path = _REGISTRY_DIR / filename
    with open(path) as f:
        return json.load(f)

SOURCE_REGISTRY = _load("source_concept_registry.json")
RECOMMENDATION_REGISTRY = _load("concept_recommendation_registry.json")

# ── Indexes ──────────────────────────────────────────────────────────────────

# concept_id → key_concept dict
CONCEPT_INDEX: Dict[str, Dict] = {
    c["concept_id"]: c for c in SOURCE_REGISTRY["key_concepts"]
}

# datasource → concept_id → {project_ids, mdl_table_refs, coverage_confidence}
SOURCE_MAP: Dict[str, Dict] = SOURCE_REGISTRY["source_concept_map"]

# concept_id → list of recommendation_area dicts
AREA_INDEX: Dict[str, List[Dict]] = {
    cid: v["recommendation_areas"]
    for cid, v in RECOMMENDATION_REGISTRY["concept_recommendations"].items()
}

# ── Query helpers ────────────────────────────────────────────────────────────

def get_concepts_for_datasource(datasource: str) -> List[Dict[str, Any]]:
    """
    Return enriched concept objects available for a given datasource.
    Each object includes concept metadata + project_ids + recommendation_areas.
    """
    ds_map = SOURCE_MAP.get(datasource, {})
    result = []
    for concept_id, source_entry in ds_map.items():
        concept_meta = CONCEPT_INDEX.get(concept_id)
        if not concept_meta:
            continue
        result.append({
            **concept_meta,
            "project_ids": source_entry["project_ids"],
            "mdl_table_refs": source_entry["mdl_table_refs"],
            "coverage_confidence": source_entry.get("coverage_confidence", 1.0),
            "recommendation_areas": AREA_INDEX.get(concept_id, []),
        })
    return result


def get_recommendation_areas(concept_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Return all recommendation_areas for a list of concept_ids, deduplicated by area_id.
    """
    seen_area_ids = set()
    areas = []
    for cid in concept_ids:
        for area in AREA_INDEX.get(cid, []):
            if area["area_id"] not in seen_area_ids:
                seen_area_ids.add(area["area_id"])
                areas.append({**area, "source_concept_id": cid})
    return areas


def get_project_ids_for_concepts(datasource: str, concept_ids: List[str]) -> List[str]:
    """
    Return deduplicated project_ids for the selected concepts on a given datasource.
    """
    ds_map = SOURCE_MAP.get(datasource, {})
    seen = set()
    result = []
    for cid in concept_ids:
        for pid in ds_map.get(cid, {}).get("project_ids", []):
            if pid not in seen:
                seen.add(pid)
                result.append(pid)
    return result


def get_mdl_tables_for_concepts(datasource: str, concept_ids: List[str]) -> List[str]:
    """
    Return deduplicated mdl_table_refs for the selected concepts.
    """
    ds_map = SOURCE_MAP.get(datasource, {})
    seen = set()
    result = []
    for cid in concept_ids:
        for tbl in ds_map.get(cid, {}).get("mdl_table_refs", []):
            if tbl not in seen:
                seen.add(tbl)
                result.append(tbl)
    return result


def match_area_by_question(
    question: str,
    concept_ids: List[str],
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Keyword-based area matching against natural_language_questions.
    Replace with vector store semantic search in production.
    """
    question_lower = question.lower()
    scored = []
    for cid in concept_ids:
        for area in AREA_INDEX.get(cid, []):
            score = sum(
                1 for q in area.get("natural_language_questions", [])
                if any(w in question_lower for w in q.lower().split())
            )
            # Also score against trigger keywords of parent concept
            concept = CONCEPT_INDEX.get(cid, {})
            score += sum(
                1 for kw in concept.get("trigger_keywords", [])
                if kw in question_lower
            )
            if score > 0:
                scored.append((score, {**area, "source_concept_id": cid}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:top_k]]


# ── Supported datasources (extend as integrations grow) ─────────────────────
SUPPORTED_DATASOURCES = [
    {
        "id": "cornerstone",
        "display_name": "Cornerstone OnDemand",
        "description": "LMS platform — training, compliance, assessments, ILT",
        "icon": "cornerstone",
    },
    # Add as integrations are built:
    # {"id": "workday", "display_name": "Workday Learning", ...},
    # {"id": "snyk", "display_name": "Snyk", "description": "Security vulnerability data", ...},
    # {"id": "sumtotal", "display_name": "SumTotal", ...},
]
```

---

## 5. Updated Orchestrator — Phase 0 Added

The orchestrator gains two new phase handlers and an updated entry point. Phases 1–3 are materially unchanged in *logic* but now reference concept and area context rather than hardcoded scoping question sets.

### Phase 0 Step A — Datasource Selection

```python
async def _handle_initial(self, user_message: str) -> Dict[str, Any]:
    """
    Entry point. If message is a datasource choice, advance to concept selection.
    Otherwise start datasource selection.
    """
    from app.agents.lexy.registry_loader import SUPPORTED_DATASOURCES
    
    self.state.phase = ConversationPhase.DATASOURCE_SELECT
    
    return {
        "phase": "datasource_select",
        "message": (
            "Hi, I'm Lexy. Before I pull any data, let me understand what you're working with. "
            "Which platform are you analysing today?"
        ),
        "options": [
            {"id": ds["id"], "label": ds["display_name"], "description": ds["description"]}
            for ds in SUPPORTED_DATASOURCES
        ],
    }


async def _handle_datasource_select(self, user_message: str) -> Dict[str, Any]:
    """User selected a datasource. Load available concepts for it."""
    from app.agents.lexy.registry_loader import (
        get_concepts_for_datasource, SUPPORTED_DATASOURCES
    )

    # Match datasource from user message
    selected_ds = None
    for ds in SUPPORTED_DATASOURCES:
        if ds["id"].lower() in user_message.lower() or ds["display_name"].lower() in user_message.lower():
            selected_ds = ds["id"]
            break

    if not selected_ds:
        # Default to first or ask again
        selected_ds = "cornerstone"

    self.state.datasource = selected_ds
    concepts = get_concepts_for_datasource(selected_ds)
    self.state.available_concepts = concepts
    self.state.phase = ConversationPhase.CONCEPT_SELECT

    return {
        "phase": "concept_select",
        "message": (
            "Great. I have data from your Cornerstone environment. "
            "Which areas do you want to explore? Pick one or more — "
            "I'll use this to focus the analysis."
        ),
        "options": [
            {
                "id": c["concept_id"],
                "label": c["display_name"],
                "description": c["description"],
                "confidence": c["coverage_confidence"],
                "sample_questions": c["business_questions"][:2],
            }
            for c in concepts
        ],
        "selection_mode": "multi",      # UI renders multi-select
        "max_selections": 3,
    }
```

### Phase 0 Step C — Concept Selection

```python
async def _handle_concept_select(self, user_message: str) -> Dict[str, Any]:
    """
    User selected concepts. Resolve project_ids, mdl_tables, and load recommendation areas.
    Then move to Phase 1.
    """
    from app.agents.lexy.registry_loader import (
        get_project_ids_for_concepts,
        get_mdl_tables_for_concepts,
        get_recommendation_areas,
    )

    # Parse selected concept IDs from user_message (option IDs sent by UI)
    selected_ids = self._parse_concept_selections(user_message)
    
    # Build SelectedConcept objects
    for c in self.state.available_concepts:
        if c["concept_id"] in selected_ids:
            self.state.selected_concepts.append(SelectedConcept(
                concept_id=c["concept_id"],
                display_name=c["display_name"],
                project_ids=c["project_ids"],
                mdl_table_refs=c["mdl_table_refs"],
                coverage_confidence=c["coverage_confidence"],
                recommendation_areas=c["recommendation_areas"],
            ))

    # Resolve project context
    project_ids = get_project_ids_for_concepts(
        self.state.datasource, selected_ids
    )
    mdl_tables = get_mdl_tables_for_concepts(
        self.state.datasource, selected_ids
    )
    
    self.state.selected_project_ids = project_ids
    self.state.active_project_id = project_ids[0] if project_ids else None
    self.state.active_mdl_tables = mdl_tables
    self.state.selected_data_sources = [self.state.datasource]

    # Preload all recommendation areas for these concepts
    all_areas = get_recommendation_areas(selected_ids)
    
    self.state.phase = ConversationPhase.INTENT_CONFIRM

    # Prompt user to ask their question, now that context is set
    concept_names = [c.display_name for c in self.state.selected_concepts]
    
    return {
        "phase": "context_ready",
        "message": (
            f"Perfect. I've loaded context for: **{', '.join(concept_names)}**. "
            f"I have {len(project_ids)} data project(s) and {len(mdl_tables)} tables in scope. "
            "What would you like to understand? Ask me in plain language."
        ),
        "context_summary": {
            "concepts": [c.display_name for c in self.state.selected_concepts],
            "project_count": len(project_ids),
            "available_areas": [
                {"id": a["area_id"], "label": a["display_name"]}
                for a in all_areas
            ],
        },
    }


def _parse_concept_selections(self, user_message: str) -> List[str]:
    """
    Match user message against available concept IDs and display names.
    UI should send concept_ids as a comma-separated string or JSON array.
    Falls back to keyword matching against display_name and trigger_keywords.
    """
    import json as _json
    # Try JSON array first (UI sends ["compliance_training", "training_roi"])
    try:
        ids = _json.loads(user_message)
        if isinstance(ids, list):
            valid = {c["concept_id"] for c in self.state.available_concepts}
            return [i for i in ids if i in valid]
    except (_json.JSONDecodeError, TypeError):
        pass

    # Keyword fallback
    msg_lower = user_message.lower()
    matched = []
    for c in self.state.available_concepts:
        if (c["concept_id"].replace("_", " ") in msg_lower or
                c["display_name"].lower() in msg_lower or
                any(kw in msg_lower for kw in c.get("trigger_keywords", []))):
            matched.append(c["concept_id"])
    return matched or [self.state.available_concepts[0]["concept_id"]]
```

---

## 6. Updated Phase 1 — Intent Confirm with Area Surfacing

Phase 1 now uses the **recommendation areas** (not hardcoded flow enums) to present the user with specific focus options. The intent classifier prompt is also concept-aware.

### Updated `_handle_intent_confirm` trigger

```python
async def _handle_question(self, user_message: str) -> Dict[str, Any]:
    """
    User has asked a question against the loaded context.
    1. Match question to recommendation area(s) using registry lookup
    2. Generate confirmation message
    3. Present area options
    """
    from app.agents.lexy.registry_loader import match_area_by_question

    self.state.user_query = user_message

    # Match areas to the question using vector store / keyword matching
    concept_ids = [c.concept_id for c in self.state.selected_concepts]
    matched_areas = match_area_by_question(user_message, concept_ids, top_k=3)

    if not matched_areas:
        # Fall back to all areas for selected concepts
        matched_areas = self.state.active_recommendation_areas[:3]

    # Generate intent confirmation via LLM using area context
    confirmation = await self._generate_area_confirmation(user_message, matched_areas)

    self.state.phase = ConversationPhase.INTENT_CONFIRM
    self.state.active_recommendation_areas = matched_areas

    return {
        "phase": "intent_confirm",
        "message": confirmation["message"],
        "options": [
            {
                "id": a["area_id"],
                "label": a["display_name"],
                "description": a["description"],
            }
            for a in matched_areas
        ] + [{"id": "other", "label": "Something else — let me describe it"}],
    }


async def _generate_area_confirmation(
    self, user_message: str, areas: List[Dict]
) -> Dict[str, Any]:
    """LLM call: given the question and matched areas, generate a confirmation message."""
    areas_text = "\n".join(
        f"- {a['display_name']}: {a['description']}"
        for a in areas
    )
    prompt = AREA_CONFIRMATION_PROMPT.format(
        user_message=user_message,
        areas=areas_text,
        concept_names=", ".join(c.display_name for c in self.state.selected_concepts),
    )
    response = await self.client.messages.create(
        model=self.model,
        max_tokens=400,
        system=prompt,
        messages=[{"role": "user", "content": "Generate the confirmation."}],
    )
    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"message": text}
```

---

## 7. Updated Phase 2 — Dynamic Scoping from Registry

Scoping questions are now **derived from the selected recommendation area's `filters` field**, not from hardcoded flow-based question sets.

```python
def _build_scoping_questions_from_area(
    self, area: Dict[str, Any]
) -> List[Dict]:
    """
    Generate scoping questions dynamically from recommendation_area.filters.
    Maps known filter names to question templates; unknown filters get a generic template.
    """
    FILTER_QUESTION_MAP = {
        "org_unit": {
            "id": "org_unit",
            "question": "Which part of the organisation should I focus on?",
            "options": ["Whole organisation", "A specific department", "A specific role or job family", "Direct reports under a manager"],
            "state_key": "org_unit",
            "option_values": ["whole_org", "department", "role", "manager"],
        },
        "time_period": {
            "id": "time_window",
            "question": "What time window matters most?",
            "options": ["Last 30 days", "Last quarter", "Year to date", "Year over year"],
            "state_key": "time_window",
            "option_values": ["last_30d", "last_quarter", "ytd", "yoy"],
        },
        "due_date_range": {
            "id": "time_window",
            "question": "Which deadline window are you concerned about?",
            "options": ["Overdue right now", "Due in the next 30 days", "Due this quarter"],
            "state_key": "time_window",
            "option_values": ["overdue_now", "next_30d", "this_quarter"],
        },
        "training_type": {
            "id": "training_type",
            "question": "What type of training is most relevant?",
            "options": ["Mandatory regulatory training", "Certifications with expiry dates", "All assigned training", "Not sure"],
            "state_key": "training_type",
            "option_values": ["mandatory", "certification", "all", "unknown"],
        },
        "delivery_method": {
            "id": "delivery_method",
            "question": "Which delivery method do you want to focus on?",
            "options": ["Instructor-led (ILT)", "eLearning / SCORM", "All methods"],
            "state_key": "additional_filters.delivery_method",
            "option_values": ["ilt", "elearning", "all"],
        },
        "audit_window": {
            "id": "audit_window",
            "question": "When is the audit?",
            "options": ["In the next 2 weeks", "Next month", "Next quarter"],
            "state_key": "additional_filters.audit_window",
            "option_values": ["2_weeks", "1_month", "1_quarter"],
        },
        "course_id": {
            "id": "course_scope",
            "question": "Do you want to focus on a specific course or programme?",
            "options": ["All courses", "A specific course (I'll specify)", "Mandatory courses only"],
            "state_key": "additional_filters.course_scope",
            "option_values": ["all", "specific", "mandatory"],
        },
    }

    questions = []
    seen_ids = set()
    for filter_name in area.get("filters", []):
        q = FILTER_QUESTION_MAP.get(filter_name)
        if q and q["id"] not in seen_ids:
            questions.append(q)
            seen_ids.add(q["id"])

    # Always include org_unit and time_period if not already added
    for default_filter in ["org_unit", "time_period"]:
        q = FILTER_QUESTION_MAP.get(default_filter)
        if q and q["id"] not in seen_ids:
            questions.append(q)
            seen_ids.add(q["id"])

    return questions[:3]  # Max 3 questions per turn
```

---

## 8. Updated Phase 3 — Metric Narration from Registry

Phase 3 now builds narration from `recommendation_area.causal_paths`, `metrics`, and `kpis` directly — no hallucination risk because the content is grounded in the registry.

### Updated `METRIC_BUILD_SYSTEM` prompt — `prompts/phase3_metric_build.py`

```python
METRIC_BUILD_SYSTEM = """
You are Lexy, generating the Phase 3 metric set narration for a user.

You have been given structured context about what will be measured. Use ONLY this context to build the narration. Do not invent metrics or causal relationships beyond what is provided.

Context:
- User question: {user_question}
- Selected recommendation area: {area_display_name}
- Area description: {area_description}
- Causal paths (use these to explain WHY): {causal_paths}
- Metrics being retrieved: {metrics}
- KPIs being highlighted: {kpis}
- Scoping: {scoping_json}
- Data sources: {data_sources}

Rules:
1. Build 3–4 plain-language sections. Each section answers ONE question the user is implicitly asking.
2. For each section, reference the causal path that explains WHY this metric is relevant.
3. Never use metric IDs, field names, or table names. Plain language only.
4. Include a confidence qualifier for every causal claim: "most likely", "typically indicates", "in most cases".
5. Keep total narration under 300 words.
6. End with 3 confirmation options.

Respond ONLY in JSON:
{
  "narration_sections": [
    {"headline": "...", "body": "..."}
  ],
  "confirmation_options": ["...", "...", "..."]
}
"""
```

### Updated `_generate_metric_narration` — grounded in registry

```python
async def _generate_metric_narration(self) -> Dict[str, Any]:
    """Generate Phase 3 narration grounded in the selected recommendation area."""
    # Get the primary active area
    area = (self.state.active_recommendation_areas or [{}])[0]

    prompt = METRIC_BUILD_SYSTEM.format(
        user_question=self.state.user_query,
        area_display_name=area.get("display_name", ""),
        area_description=area.get("description", ""),
        causal_paths=json.dumps(area.get("causal_paths", []), indent=2),
        metrics=", ".join(area.get("metrics", [])),
        kpis=", ".join(area.get("kpis", [])),
        scoping_json=self.state.scoping.model_dump_json(indent=2),
        data_sources=", ".join(self.state.selected_data_sources),
    )
    response = await self.client.messages.create(
        model=self.model,
        max_tokens=700,
        system=prompt,
        messages=[{"role": "user", "content": "Generate the metric narration."}],
    )
    text = response.content[0].text.strip()
    try:
        parsed = json.loads(text)
        sections = parsed.get("narration_sections", [])
        narration_text = "\n\n".join(
            f"**{s['headline']}** {s['body']}" for s in sections
        )
        return {
            "narration_text": narration_text,
            "confirmation_options": parsed.get("confirmation_options", []),
        }
    except json.JSONDecodeError:
        return {"narration_text": text, "confirmation_options": []}
```

---

## 9. Updated Workflow Bridge — Registry-Backed State Construction

```python
def build_csod_initial_state(state: ConversationState) -> dict:
    """
    Build CSOD initial state from ConversationState, injecting registry-resolved context.
    """
    # Get the primary selected area for data_requirements
    primary_area = (state.active_recommendation_areas or [{}])[0]
    
    compliance_profile = {
        # Standard scoping
        "time_window": state.scoping.time_window or "last_quarter",
        "org_unit": state.scoping.org_unit or "whole_org",
        "org_unit_value": state.scoping.org_unit_value,
        "training_type": state.scoping.training_type,
        "persona": state.scoping.persona or _infer_persona(state),
        "flow": state.flow.value,
        "lexy_metric_narration": state.metric_narration,

        # NEW: registry-resolved context — consumed by csod_planner and csod_mdl_schema_retrieval
        "selected_concepts": [c.concept_id for c in state.selected_concepts],
        "selected_area_ids": state.selected_area_ids,
        "priority_metrics": primary_area.get("metrics", []),
        "priority_kpis": primary_area.get("kpis", []),
        "data_requirements": primary_area.get("data_requirements", []),
        "causal_paths": primary_area.get("causal_paths", []),
        "active_mdl_tables": state.active_mdl_tables,
        "additional_filters": state.scoping.additional_filters,
    }

    common_kwargs = dict(
        user_query=state.user_query,
        session_id=state.session_id,
        active_project_id=state.active_project_id,
        selected_data_sources=state.selected_data_sources,
        compliance_profile=compliance_profile,
        causal_graph_enabled=state.causal_graph_enabled,
        causal_vertical="lms",
    )

    if state.use_advisor_workflow:
        return create_csod_metric_advisor_initial_state(**common_kwargs)
    else:
        return create_csod_initial_state(**common_kwargs)
```

---

## 10. Changes to `csod_nodes.py`

### 10.1 `csod_intent_classifier_node` — Already updated (v1 bypass intact)
No additional changes needed. The bypass handles `lexy_metric_narration` + `csod_intent` pass-through.

### 10.2 `csod_mdl_schema_retrieval_node` — NEW: Use `active_mdl_tables` as pre-filter

```python
# In csod_mdl_schema_retrieval_node:
def csod_mdl_schema_retrieval_node(state: CSOD_State) -> CSOD_State:
    profile = state.get("compliance_profile", {})
    
    # If Lexy resolved MDL tables from registry, use as retrieval pre-filter
    active_mdl_tables = profile.get("active_mdl_tables", [])
    data_requirements = profile.get("data_requirements", [])
    
    # Combine: data_requirements are the minimal required set; active_mdl_tables is the full set
    priority_tables = list(set(data_requirements + active_mdl_tables[:20]))  # cap at 20
    
    if priority_tables:
        logger.info(f"MDL schema retrieval: using registry-resolved table filter ({len(priority_tables)} tables)")
        # Pass priority_tables as retrieval filter hint to csod_retrieve_mdl_schemas
        state["csod_mdl_table_filter"] = priority_tables

    # ... rest of existing retrieval logic unchanged
```

### 10.3 `csod_metrics_retrieval_node` — NEW: Pre-seed priority metrics from registry

```python
# In csod_metrics_retrieval_node:
def csod_metrics_retrieval_node(state: CSOD_State) -> CSOD_State:
    profile = state.get("compliance_profile", {})
    priority_metrics = profile.get("priority_metrics", [])
    priority_kpis = profile.get("priority_kpis", [])

    if priority_metrics:
        # Pre-seed the retrieval target list so the metrics retriever
        # searches for these by name first before doing semantic expansion
        state["csod_priority_metric_names"] = priority_metrics
        state["csod_priority_kpi_names"] = priority_kpis
        logger.info(f"Metrics retrieval: registry seeded {len(priority_metrics)} priority metrics")

    # ... rest of existing retrieval logic unchanged
```

### 10.4 `csod_planner_node` — NEW: Inject causal_paths and selected_area into plan

```python
# In csod_planner_node, add to human_message context:
causal_paths = profile.get("causal_paths", [])
selected_concepts = profile.get("selected_concepts", [])
selected_area_ids = profile.get("selected_area_ids", [])

if causal_paths:
    human_message += f"\n\nKnown causal paths for this analysis:\n{json.dumps(causal_paths, indent=2)}"
if selected_concepts:
    human_message += f"\n\nUser-selected concept domains: {', '.join(selected_concepts)}"
if selected_area_ids:
    human_message += f"\n\nFocus recommendation areas: {', '.join(selected_area_ids)}"
```

---

## 11. New Prompt — `prompts/phase1_area_confirmation.py`

```python
AREA_CONFIRMATION_PROMPT = """
You are Lexy. The user has asked a question against their selected LMS data.
You have matched their question to one or more analysis areas.

User question: {user_message}
Selected concepts: {concept_names}
Matched analysis areas:
{areas}

Generate a brief confirmation message (2–3 sentences max) that:
1. Restates what the user is trying to understand in plain language
2. Mentions which area(s) are most relevant
3. Asks if they want to proceed with those areas

Do NOT use metric names, table names, or technical identifiers.

Respond in JSON:
{{
  "message": "<confirmation message>",
  "primary_area_id": "<area_id of the best match>"
}}
"""
```

---

## 12. Updated API Response Contract

The conversation API now returns richer context in Phase 0 responses:

```python
class ConversationResponse(BaseModel):
    session_id: str
    phase: str
    message: str

    # Phase 0A
    datasource_options: list = []

    # Phase 0B+C
    concept_options: list = []
    context_summary: Optional[dict] = None

    # Phase 1
    area_options: list = []

    # Phase 2
    scoping_questions: list = []

    # Phase 3
    metric_narration: Optional[str] = None
    confirmation_options: list = []

    # Phase 4
    csod_initial_state: Optional[dict] = None
    use_advisor_workflow: bool = False
```

---

## 13. Full Phase Transition Table

| Current Phase | User Action | Next Phase | State Changes |
|---|---|---|---|
| `initial` | Any message | `datasource_select` | — |
| `datasource_select` | Picks datasource | `concept_select` | `datasource`, `available_concepts` set |
| `concept_select` | Picks concepts | `context_ready` → awaits question | `selected_concepts`, `project_ids`, `mdl_tables` resolved |
| `context_ready` | Asks a question | `intent_confirm` | `user_query`, `active_recommendation_areas` matched |
| `intent_confirm` | Confirms area | `scoping` | `selected_area_ids`, `active_recommendation_areas` locked |
| `scoping` | Answers questions | `scoping` (if more) / `metric_build` | `scoping.*` fields filled; if done → calls `_generate_metric_narration()` |
| `metric_build` | Confirms metric set | `confirmed` | `csod_initial_state` built + returned to caller |
| `confirmed` | — | `pipeline_running` | CSOD pipeline invoked by API layer |

---

## 14. Implementation Sequence for Cursor

### Step 1 — Registry loader (no deps)
**File:** `app/agents/lexy/registry_loader.py`  
Copy JSON files to `data/registries/`. Implement all 6 helper functions.  
**Test:** Unit test all helpers against fixture data. Assert `get_concepts_for_datasource("cornerstone")` returns 10 concepts; `get_project_ids_for_concepts("cornerstone", ["compliance_training"])` returns 16 IDs.

### Step 2 — Updated ConversationState
**File:** `app/agents/lexy/conversation_state.py`  
Add `SelectedConcept` model and all new Phase 0 fields.  
**Test:** `ConversationState(session_id="x", datasource="cornerstone")` round-trips through JSON.

### Step 3 — Phase 0 handlers
**Files:** `conversational_orchestrator.py` (add `_handle_datasource_select`, `_handle_concept_select`, `_parse_concept_selections`)  
**Test:** Feed "cornerstone" → assert `state.datasource == "cornerstone"` and `len(state.available_concepts) == 10`. Feed `["compliance_training", "training_roi"]` → assert correct project_ids resolved.

### Step 4 — Phase 1 area matching + confirmation
**Files:** `conversational_orchestrator.py` (`_handle_question`, `_generate_area_confirmation`), `prompts/phase1_area_confirmation.py`  
**Test:** Feed "Why is our compliance rate dropping?" with concept `compliance_training` selected → assert `matched_areas[0]["area_id"]` is one of `["overdue_risk", "completion_trends"]`.

### Step 5 — Phase 2 dynamic scoping
**Files:** `conversational_orchestrator.py` (`_build_scoping_questions_from_area`)  
**Test:** For area `audit_readiness` (filters: `audit_window, org_unit, requirement_tag, certification_status`), assert questions include `audit_window` and `org_unit` entries.

### Step 6 — Phase 3 registry-grounded narration
**Files:** `prompts/phase3_metric_build.py` (update), `conversational_orchestrator.py` (`_generate_metric_narration` update)  
**Test:** Mock LLM response. Assert prompt sent to LLM contains `causal_paths` from `overdue_risk` area.

### Step 7 — Updated workflow bridge
**File:** `app/agents/lexy/workflow_bridge.py`  
Assert `compliance_profile` contains `selected_concepts`, `priority_metrics`, `data_requirements`, `active_mdl_tables`.

### Step 8 — CSOD node updates
**File:** `app/agents/csod/csod_nodes.py`  
Add `active_mdl_tables` filter to `csod_mdl_schema_retrieval_node`.  
Add `priority_metrics` pre-seed to `csod_metrics_retrieval_node`.  
Add causal context injection to `csod_planner_node`.  
**Test:** Build a state with `compliance_profile.active_mdl_tables = ["transcript_core", "training_assignment_core"]` and assert `csod_mdl_table_filter` is set before the schema retrieval call.

### Step 9 — API contract update
**File:** `api/routes/lexy_conversation.py`  
Update `ConversationResponse` model. Update session handler to route Phase 0 messages correctly.

### Step 10 — End-to-end integration test
Simulate a full 7-turn conversation:  
Turn 1: initial → datasource options  
Turn 2: "Cornerstone" → concept options  
Turn 3: `["compliance_training"]` → context_ready  
Turn 4: "Why is our compliance rate dropping?" → area options  
Turn 5: "completion_trends" → scoping questions  
Turn 6: scoping answers → metric narration  
Turn 7: "Show me the dashboard" → `csod_initial_state` with `active_project_id`, `priority_metrics`, `data_requirements` all populated from registry.

---

## 15. Open Decisions (updated from v1)

| Decision | Options | Recommendation |
|---|---|---|
| `match_area_by_question` backend | Keyword scoring (implemented above) vs. vector store semantic search | **Vector store** for production — query against `area.description + natural_language_questions` embeddings; keyword version is dev stub |
| Multi-concept area deduplication | First-match wins vs. weighted merge by `coverage_confidence` | **First-match wins** initially; merge later when multi-concept conflicts become real |
| `active_project_id` (singular) vs. `selected_project_ids` (plural) | CSOD initial state currently takes a single `active_project_id` | Keep singular as primary; pass full list in `compliance_profile.selected_project_ids` for nodes that can use it |
| Phase 0 datasource selection — UI vs. chat | Button click vs. typed message | **Both**: UI sends datasource ID as a structured message; orchestrator accepts either format |
| Concept selection persistence | Per-session only vs. user profile | **Per-session** now; add to user memory layer later |