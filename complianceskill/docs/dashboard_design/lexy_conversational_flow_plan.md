# Lexy Conversational Flow — Implementation Plan
## Cursor Implementation Guide

**Scope:** End-to-end conversational pre-pipeline layer for Lexy AI  
**Integrates with:** `csod_workflow.py`, `csod_metric_advisor_workflow.py`  
**Architecture:** New `app/agents/lexy/` module — multi-turn orchestrator that collects user context across 3 phases, resolves `active_project_id` via a ProjectSelector tool, then fires the backend CSOD pipeline with a fully-populated initial state.

---

## 1. Architecture Overview

```
User → LexyConversationalOrchestrator
          │
          ├─ Phase 1: Intent Classification + Confirmation
          ├─ Phase 2: Scoping (org unit, time window, training type)
          ├─ Phase 3: Metric Set Narration + User Confirmation
          │
          ├─ [ProjectSelectorTool called at end of Phase 2]
          │      active_project_id resolved from scoping answers
          │
          └─ WorkflowBridge.build_initial_state()
                │
                ├─ csod_workflow  (Flow 1, 2, 3, 4 with metrics/dashboard intents)
                └─ csod_metric_advisor_workflow  (metric_kpi_advisor intent)
```

The orchestrator is a **separate LangGraph workflow** (or a simple async multi-turn loop). It does NOT run any CSOD nodes. Its only job is conversation management. When Phase 3 confirmation is received, it terminates and returns a fully-constructed `initial_state` dict to the caller, which then invokes the CSOD pipeline.

---

## 2. Flow → CSOD Intent Mapping

| Lexy Flow | Trigger Pattern | CSOD Intent | Causal Graph | Advisor? |
|---|---|---|---|---|
| Flow 1 — Compliance Risk | "compliance rate dropping", "overdue", "audit" | `metrics_dashboard_plan` | ✅ enabled | No |
| Flow 2 — Skills Gap | "skills gap", "readiness", "succession" | `metrics_recommender_with_gold_plan` | ✅ enabled | No |
| Flow 3 — Learning Effectiveness | "program effectiveness", "training impact", "content performance" | `dashboard_generation_for_persona` | Optional | No |
| Flow 4 — Training ROI | "cost", "budget", "no-shows", "ROI", "vendor" | `metrics_dashboard_plan` | Optional | No |
| Metric/KPI Advisor | "recommend KPIs", "what should I measure", "metric advice" | `metric_kpi_advisor` | ✅ enabled | **Yes** |

---

## 3. File Structure

```
app/
  agents/
    lexy/
      __init__.py
      conversation_state.py              # ConversationState, ScopingAnswers Pydantic models
      conversational_orchestrator.py     # Main multi-turn LangGraph workflow
      phase_router.py                    # Phase transition logic
      project_selector_tool.py           # ProjectSelectorTool (dummy + interface for real)
      workflow_bridge.py                 # Converts ConversationState → CSOD initial state
      prompts/
        __init__.py
        system_prompt.py                 # Lexy persona + universal rules
        phase1_intent_confirm.py         # Intent classification + confirmation message
        phase2_scoping.py                # Scoping questions per flow
        phase3_metric_build.py           # Metric set narration generator
        flows/
          flow1_compliance_risk.py       # Flow 1 specific prompts
          flow2_skills_gap.py            # Flow 2 specific prompts
          flow3_learning_effectiveness.py
          flow4_training_roi.py
          flow_metric_advisor.py         # Metric/KPI advisor flow prompts
```

---

## 4. Data Models — `conversation_state.py`

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class LexyFlow(str, Enum):
    COMPLIANCE_RISK = "compliance_risk"
    SKILLS_GAP = "skills_gap"
    LEARNING_EFFECTIVENESS = "learning_effectiveness"
    TRAINING_ROI = "training_roi"
    METRIC_ADVISOR = "metric_kpi_advisor"
    UNKNOWN = "unknown"

class ConversationPhase(str, Enum):
    INITIAL = "initial"
    INTENT_CONFIRM = "intent_confirm"        # Phase 1: Lexy confirms the use case
    SCOPING = "scoping"                      # Phase 2: 2-3 targeted questions
    METRIC_BUILD = "metric_build"            # Phase 3: Metric set narration
    CONFIRMED = "confirmed"                  # User confirmed → fire pipeline
    PIPELINE_RUNNING = "pipeline_running"
    DASHBOARD = "dashboard"                  # Phase 4: Dashboard presented

class ScopingAnswers(BaseModel):
    org_unit: Optional[str] = None           # "whole_org" | "department" | "role" | "manager"
    org_unit_value: Optional[str] = None     # Specific dept/role name if given
    time_window: Optional[str] = None        # "last_30d" | "last_quarter" | "ytd" | "yoy"
    training_type: Optional[str] = None      # "mandatory" | "certification" | "all" | None
    onset_pattern: Optional[str] = None      # "gradual" | "sudden" | "chronic"
    breadth: Optional[str] = None            # "widespread" | "concentrated" | "unknown"
    persona: Optional[str] = None            # "l&d_manager" | "chro" | "compliance_officer"
    # ROI/cost specific
    cost_focus: Optional[str] = None         # "no_shows" | "vendor_efficiency" | "full_roi"
    # Skills specific
    skills_domain: Optional[str] = None      # "technical" | "leadership" | "compliance"

class ConversationState(BaseModel):
    session_id: str
    user_query: str                           # Original opening question
    flow: LexyFlow = LexyFlow.UNKNOWN
    phase: ConversationPhase = ConversationPhase.INITIAL
    scoping: ScopingAnswers = Field(default_factory=ScopingAnswers)
    messages: List[Dict[str, str]] = Field(default_factory=list)
    
    # Resolved by ProjectSelectorTool
    active_project_id: Optional[str] = None
    selected_data_sources: List[str] = Field(default_factory=list)
    project_selector_confidence: float = 0.0
    
    # Metric narration produced in Phase 3
    metric_narration: Optional[str] = None
    
    # Populated once confirmed → passed to CSOD pipeline
    csod_intent: Optional[str] = None
    causal_graph_enabled: bool = True
    use_advisor_workflow: bool = False
    
    # UI scaffolding
    pending_question: Optional[str] = None   # Currently-awaiting question text
    options_presented: List[str] = Field(default_factory=list)
```

---

## 5. ProjectSelector Tool — `project_selector_tool.py`

The ProjectSelectorTool maps `(flow, scoping_answers, data_sources)` to an `active_project_id`. In production this queries a `projects` table. For now, implement a **dummy registry** with realistic structure so the interface is correct and swappable.

```python
from dataclasses import dataclass
from typing import Optional, List
from app.agents.lexy.conversation_state import LexyFlow, ScopingAnswers

@dataclass
class ProjectMatch:
    project_id: str
    project_name: str
    data_sources: List[str]
    confidence: float
    reason: str

# ── Dummy Registry ──────────────────────────────────────────────────────────
# Replace with DB lookup in production.
# Structure: (flow, org_unit, data_sources) → project_id

DUMMY_PROJECT_REGISTRY = [
    {
        "project_id": "proj_csod_compliance_001",
        "project_name": "Cornerstone Compliance Training Analytics",
        "flows": [LexyFlow.COMPLIANCE_RISK],
        "data_sources": ["cornerstone"],
        "org_units": ["whole_org", "department", "role", "manager"],
    },
    {
        "project_id": "proj_csod_skills_001",
        "project_name": "Cornerstone Skills Gap Intelligence",
        "flows": [LexyFlow.SKILLS_GAP, LexyFlow.METRIC_ADVISOR],
        "data_sources": ["cornerstone", "workday"],
        "org_units": ["whole_org", "department", "role"],
    },
    {
        "project_id": "proj_csod_effectiveness_001",
        "project_name": "Learning Program Effectiveness",
        "flows": [LexyFlow.LEARNING_EFFECTIVENESS],
        "data_sources": ["cornerstone"],
        "org_units": ["whole_org", "department"],
    },
    {
        "project_id": "proj_csod_roi_001",
        "project_name": "Training ROI and ILT Cost Intelligence",
        "flows": [LexyFlow.TRAINING_ROI],
        "data_sources": ["cornerstone"],
        "org_units": ["whole_org"],
    },
    {
        "project_id": "proj_csod_kpi_001",
        "project_name": "LMS KPI Advisory",
        "flows": [LexyFlow.METRIC_ADVISOR, LexyFlow.COMPLIANCE_RISK, LexyFlow.SKILLS_GAP],
        "data_sources": ["cornerstone", "workday"],
        "org_units": ["whole_org", "department", "role"],
    },
]


def select_project(
    flow: LexyFlow,
    scoping: ScopingAnswers,
    data_sources: List[str] = None,
) -> ProjectMatch:
    """
    Select the best matching project for the given flow and scoping context.
    
    In production: replace dummy registry with a DB query against a `projects`
    table filtered by tenant_id, data_source integrations, and use-case tags.
    """
    data_sources = data_sources or ["cornerstone"]
    
    candidates = []
    for entry in DUMMY_PROJECT_REGISTRY:
        flow_match = flow in entry["flows"]
        ds_overlap = bool(set(data_sources) & set(entry["data_sources"]))
        org_match = (scoping.org_unit or "whole_org") in entry["org_units"]
        
        score = (0.5 * flow_match) + (0.3 * ds_overlap) + (0.2 * org_match)
        if score > 0.4:
            candidates.append((score, entry))
    
    if not candidates:
        # Fallback to first project that matches flow
        for entry in DUMMY_PROJECT_REGISTRY:
            if flow in entry["flows"]:
                return ProjectMatch(
                    project_id=entry["project_id"],
                    project_name=entry["project_name"],
                    data_sources=entry["data_sources"],
                    confidence=0.5,
                    reason="fallback_flow_match",
                )
    
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]
    return ProjectMatch(
        project_id=best["project_id"],
        project_name=best["project_name"],
        data_sources=best["data_sources"],
        confidence=best_score,
        reason="registry_match",
    )
```

---

## 6. Prompts

### 6.1 System Prompt — `prompts/system_prompt.py`

```python
LEXY_SYSTEM_PROMPT = """
You are Lexy, an AI intelligence layer for HR and L&D platforms (Cornerstone OnDemand, Workday).

Your role is to guide the user from a natural language question to a fully populated analytics dashboard through a structured conversation. You do not surface raw metric names, technical field identifiers, or internal system IDs. Every response is in plain language.

Rules you always follow:
1. Never present correlation as causation. Every causal claim must include a confidence qualifier.
2. Never surface metric IDs, table names, or field names to the user.
3. Never recommend the same intervention twice if the user has indicated it was tried previously.
4. When you describe what you are about to measure, explain the *reasoning* — not just the metric name.
5. Always give the user 2–4 discrete choices where possible. Open-ended questions are a last resort.
6. Keep your responses concise and direct. Do not pad with filler language.

You are currently in the {phase} phase of the conversation.
The identified use case is: {flow}.
Session ID: {session_id}
"""
```

---

### 6.2 Phase 1 — Intent Classifier Prompt — `prompts/phase1_intent_confirm.py`

This prompt is used by an LLM call to classify the user's opening question into a `LexyFlow` and generate the Phase 1 confirmation message.

```python
INTENT_CLASSIFIER_SYSTEM = """
You are a classifier for an LMS intelligence system.

Given the user's opening question, identify:
1. The most likely use case (flow)
2. The opening clarifying questions to ask

Available flows and their signal patterns:

COMPLIANCE_RISK:
  Signals: "compliance rate", "overdue", "mandatory training", "audit", "missed deadlines", "regulatory"
  
SKILLS_GAP:
  Signals: "skills gap", "skill readiness", "succession", "capability", "role competency", "upskilling"
  
LEARNING_EFFECTIVENESS:
  Signals: "program effectiveness", "did the training work", "knowledge retention", "content performance", "completion vs learning"
  
TRAINING_ROI:
  Signals: "cost", "budget", "ROI", "no-shows", "cancellations", "vendor spend", "cost per learner", "ILT efficiency"
  
METRIC_ADVISOR:
  Signals: "what should I measure", "recommend KPIs", "metric advice", "what metrics matter", "dashboard KPIs"

Respond ONLY with valid JSON matching this schema:
{
  "flow": "<COMPLIANCE_RISK|SKILLS_GAP|LEARNING_EFFECTIVENESS|TRAINING_ROI|METRIC_ADVISOR|UNKNOWN>",
  "confidence": <0.0–1.0>,
  "confirmation_message": "<Lexy's Phase 1 message confirming the use case>",
  "confirmation_options": ["<option 1>", "<option 2>", "<option 3 if relevant>"]
}

The confirmation_message should restate the user's goal in plain language and ask if that's right.
The confirmation_options are the choices presented to the user (Yes variants + a redirect).
"""

# ── Per-flow confirmation message templates ──────────────────────────────────
# Used as few-shot examples in the prompt or as fallbacks.

FLOW_CONFIRMATIONS = {
    "compliance_risk": {
        "message": (
            "It looks like you're trying to understand what's driving your compliance training risk "
            "— not just who is overdue, but why the overdue numbers are building up and what to do about it. "
            "Is that right?"
        ),
        "options": [
            "Yes, I want to understand the root cause",
            "Yes, and I also need to report this to leadership",
            "Actually I just need a list of overdue employees",
        ],
    },
    "skills_gap": {
        "message": (
            "It sounds like you want to understand where there are capability gaps in your workforce "
            "— which roles or teams are underprepared, and whether your current learning programmes "
            "are closing those gaps. Is that right?"
        ),
        "options": [
            "Yes, I want to see where the gaps are and what's driving them",
            "Yes, and I need to build a business case for targeted programmes",
            "I mainly need a skills inventory report",
        ],
    },
    "learning_effectiveness": {
        "message": (
            "It sounds like you want to evaluate whether your training programmes are actually "
            "changing behaviour or performance — not just whether people are completing them. Is that right?"
        ),
        "options": [
            "Yes, I want to understand whether training is leading to real improvement",
            "Yes, and I want to identify which programmes to prioritise or cut",
            "I mainly want to see completion and pass rate data",
        ],
    },
    "training_roi": {
        "message": (
            "It sounds like you want to understand where your training budget is going — "
            "and specifically what proportion is being spent on learning that actually happens "
            "versus cost committed to training that was cancelled, not attended, or rushed through. Is that right?"
        ),
        "options": [
            "Yes, I want to quantify the waste in our training spend",
            "Yes, and I need to build a business case for the CFO",
            "I mainly want to see ILT utilisation and vendor spend",
        ],
    },
    "metric_kpi_advisor": {
        "message": (
            "It sounds like you want advice on which metrics and KPIs you should be tracking "
            "for your LMS — and you want the reasoning behind the recommendations, not just a list. "
            "Is that right?"
        ),
        "options": [
            "Yes, recommend KPIs with the reasoning behind each one",
            "Yes, and map them to a dashboard layout",
            "I want to compare what I'm currently measuring against what I should be measuring",
        ],
    },
}
```

---

### 6.3 Phase 2 — Scoping Prompt — `prompts/phase2_scoping.py`

```python
# Scoping question sets per flow.
# Each entry has: question text + options.
# The orchestrator presents these sequentially or combined (max 3 per turn).

SCOPING_QUESTIONS = {
    "compliance_risk": [
        {
            "id": "breadth",
            "question": "Are you seeing this across the whole company or in specific areas?",
            "options": [
                "Seems widespread",
                "Concentrated in a few departments",
                "Not sure — that's what I want to find out",
            ],
            "state_key": "breadth",
            "option_values": ["widespread", "concentrated", "unknown"],
        },
        {
            "id": "onset_pattern",
            "question": "When did the compliance rate start to change?",
            "options": [
                "It's been declining for a few months",
                "It dropped suddenly in the last few weeks",
                "It's always been a problem but it's getting worse",
            ],
            "state_key": "onset_pattern",
            "option_values": ["gradual", "sudden", "chronic"],
        },
        {
            "id": "training_type",
            "question": "What type of training is most affected?",
            "options": [
                "Mandatory regulatory compliance training",
                "Certifications with expiry dates",
                "All assigned training in general",
                "I'm not sure",
            ],
            "state_key": "training_type",
            "option_values": ["mandatory", "certification", "all", "unknown"],
        },
    ],

    "skills_gap": [
        {
            "id": "org_unit",
            "question": "Which part of the organisation are you most focused on?",
            "options": [
                "The whole organisation",
                "A specific department or function",
                "A specific role family or job level",
                "A team preparing for a specific transition or project",
            ],
            "state_key": "org_unit",
            "option_values": ["whole_org", "department", "role", "transition_team"],
        },
        {
            "id": "skills_domain",
            "question": "What type of skills are you most concerned about?",
            "options": [
                "Technical or role-specific skills",
                "Leadership and management capability",
                "Compliance and regulatory knowledge",
                "All of the above",
            ],
            "state_key": "skills_domain",
            "option_values": ["technical", "leadership", "compliance", "all"],
        },
        {
            "id": "time_window",
            "question": "What time window matters most?",
            "options": [
                "Current state — where are we right now",
                "Trend over the last quarter",
                "Year-over-year comparison",
            ],
            "state_key": "time_window",
            "option_values": ["current", "last_quarter", "yoy"],
        },
    ],

    "learning_effectiveness": [
        {
            "id": "org_unit",
            "question": "Which population are you evaluating?",
            "options": [
                "The whole organisation",
                "A specific programme or curriculum",
                "A specific department or role",
                "New hires or onboarding cohorts",
            ],
            "state_key": "org_unit",
            "option_values": ["whole_org", "programme", "department", "new_hire"],
        },
        {
            "id": "effectiveness_lens",
            "question": "What does 'effectiveness' mean in your context right now?",
            "options": [
                "Whether people are actually learning (knowledge retention)",
                "Whether training is changing behaviour or performance on the job",
                "Whether learners are engaging meaningfully versus rushing through",
                "Whether the right people are taking the right training",
            ],
            "state_key": "training_type",
            "option_values": ["retention", "behaviour_change", "engagement_quality", "targeting"],
        },
        {
            "id": "time_window",
            "question": "Time window?",
            "options": [
                "Last 30 days",
                "Last quarter",
                "Year to date",
                "Comparing this year to last year",
            ],
            "state_key": "time_window",
            "option_values": ["last_30d", "last_quarter", "ytd", "yoy"],
        },
    ],

    "training_roi": [
        {
            "id": "cost_focus",
            "question": "What's your primary concern right now?",
            "options": [
                "Understanding where money is being wasted (no-shows, cancellations)",
                "Comparing vendor cost efficiency",
                "Building a full ROI case for leadership",
                "Explaining why cost per learner has changed",
            ],
            "state_key": "cost_focus",
            "option_values": ["waste", "vendor_efficiency", "full_roi", "cost_decomposition"],
        },
        {
            "id": "org_unit",
            "question": "Which scope should I use?",
            "options": [
                "Whole organisation",
                "A specific department or cost centre",
                "A specific training programme or vendor",
            ],
            "state_key": "org_unit",
            "option_values": ["whole_org", "department", "programme"],
        },
        {
            "id": "time_window",
            "question": "Time window?",
            "options": [
                "Last quarter",
                "Year to date",
                "Full last year",
                "Comparing this year to last year",
            ],
            "state_key": "time_window",
            "option_values": ["last_quarter", "ytd", "last_year", "yoy"],
        },
    ],

    "metric_kpi_advisor": [
        {
            "id": "org_unit",
            "question": "Which audience is this dashboard or KPI set for?",
            "options": [
                "CHRO or executive leadership",
                "L&D manager or learning operations",
                "Compliance officer",
                "Business unit leader or department head",
            ],
            "state_key": "persona",
            "option_values": ["chro", "ld_manager", "compliance_officer", "business_unit"],
        },
        {
            "id": "skills_domain",
            "question": "Which area do you want KPI recommendations for?",
            "options": [
                "Compliance training coverage and risk",
                "Skills development and capability building",
                "Learning programme ROI and cost efficiency",
                "Overall LMS health and engagement",
            ],
            "state_key": "skills_domain",
            "option_values": ["compliance", "skills", "roi", "engagement"],
        },
    ],
}

SCOPING_INTRO = {
    "compliance_risk": "A few more questions to make sure I'm looking in the right place:",
    "skills_gap": "Let me ask a couple of questions to focus the analysis:",
    "learning_effectiveness": "To make sure I'm measuring the right things:",
    "training_roi": "A couple of questions before I pull the cost picture together:",
    "metric_kpi_advisor": "To give you the most relevant KPI recommendations:",
}
```

---

### 6.4 Phase 3 — Metric Build Prompt — `prompts/phase3_metric_build.py`

This is the most important prompt — it generates Lexy's plain-language explanation of what metrics are being assembled and why. It runs **after** `ProjectSelectorTool` resolves the `active_project_id` but **before** the CSOD pipeline executes.

```python
METRIC_BUILD_SYSTEM = """
You are Lexy, generating the Phase 3 metric set narration for a user.

You have the following context:
- Flow: {flow}
- Scoping answers: {scoping_json}
- Resolved project: {project_name}
- Data sources available: {data_sources}

Generate a plain-language explanation of what you are going to measure and WHY.

Rules:
1. Do NOT name internal metric IDs, field names, or table names.
2. Structure the narration as 3–5 thematic sections. Each section:
   - States what you are measuring (the question it answers)
   - Explains WHY this is the right thing to look at given what the user told you
   - Describes what a notable finding in this area would indicate
3. Every causal claim must include a qualifier like "most likely", "typically indicates", or "in most cases".
4. End with 3 confirmation options the user can select to proceed.
5. Keep the total narration under 350 words.

Respond ONLY with valid JSON:
{
  "narration_sections": [
    {
      "headline": "<Short section title>",
      "body": "<2–3 sentence explanation>"
    }
  ],
  "confirmation_options": [
    "<Option 1 — proceed as described>",
    "<Option 2 — add a comparison layer>",
    "<Option 3 — narrow to a specific group>"
  ]
}
"""
```

---

### 6.5 Flow-Specific Metric Narration Templates — `prompts/flows/`

Pre-built narration structures for each flow. The LLM call in Phase 3 uses these as strong few-shot examples. In lower-latency mode, these can be used directly with variable substitution instead of an LLM call.

**`flow1_compliance_risk.py`**

```python
COMPLIANCE_RISK_NARRATION_TEMPLATE = """
Based on what you've told me, here's what I'm pulling together and why:

**The assignment load picture.** The most common reason compliance rates drop isn't disengagement — it's that too many trainings have been assigned in the same window. I'll check whether the volume of compliance assignments has increased relative to the same period {time_window_comparison}, which would explain why completion rates are falling even if people are actively logging in.

**Engagement signals.** There's an important difference between someone overwhelmed by volume and someone who has disengaged entirely. I'll look at whether login frequency and active learning sessions have changed alongside completion rates. Stable logins with falling completions {breadth_context} points to a capacity or assignment problem. Falling logins suggest a different intervention is needed.

**The overdue and missed-deadline pattern.** I'll check whether overdue training is {breadth_distribution}. Concentrated patterns typically indicate a local management or scheduling issue. Widespread patterns suggest a systemic assignment or platform problem.

**How completions are actually happening.** I'll look at the proportion of training completed in a single rapid session — a signal for rushed completions that inflate the compliance rate number without delivering learning. This matters because it determines whether your compliance rate is a genuine signal or a vanity number.
"""

COMPLIANCE_RISK_CONFIRMATION_OPTIONS = [
    "This sounds right — show me the dashboard",
    "Can you also include last year's numbers for comparison?",
    "I only need to see the teams that are at risk right now",
]
```

---

## 7. Orchestrator — `conversational_orchestrator.py`

```python
"""
LexyConversationalOrchestrator

A multi-turn conversation manager that runs Phases 1–3 of the Lexy flow,
then returns a fully-constructed initial state for the CSOD pipeline.

Usage:
    orchestrator = LexyConversationalOrchestrator(session_id="abc")
    
    # Turn 1
    response = await orchestrator.process_message("Why is our compliance training rate dropping?")
    # → {"phase": "intent_confirm", "message": "...", "options": [...]}
    
    # Turn 2
    response = await orchestrator.process_message("Yes, I want to understand the root cause")
    # → {"phase": "scoping", "message": "...", "questions": [...]}
    
    # ... scoping turns ...
    
    # Final turn
    response = await orchestrator.process_message("This sounds right — show me the dashboard")
    # → {"phase": "confirmed", "csod_initial_state": {...}}
    #   Caller invokes csod_app.invoke(csod_initial_state) 
"""

import json
import uuid
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic

from app.agents.lexy.conversation_state import (
    ConversationState, ConversationPhase, LexyFlow, ScopingAnswers
)
from app.agents.lexy.project_selector_tool import select_project
from app.agents.lexy.workflow_bridge import build_csod_initial_state
from app.agents.lexy.prompts.system_prompt import LEXY_SYSTEM_PROMPT
from app.agents.lexy.prompts.phase1_intent_confirm import (
    INTENT_CLASSIFIER_SYSTEM, FLOW_CONFIRMATIONS
)
from app.agents.lexy.prompts.phase2_scoping import SCOPING_QUESTIONS, SCOPING_INTRO
from app.agents.lexy.prompts.phase3_metric_build import METRIC_BUILD_SYSTEM


class LexyConversationalOrchestrator:

    def __init__(self, session_id: str = None, model: str = "claude-sonnet-4-20250514"):
        self.client = AsyncAnthropic()
        self.model = model
        self.state = ConversationState(
            session_id=session_id or str(uuid.uuid4()),
            user_query="",
        )
        self._scoping_queue: List[Dict] = []   # remaining scoping questions

    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """
        Process a single user message and advance the conversation phase.
        Returns a dict with at minimum: {"phase": str, "message": str}.
        When phase == "confirmed", also includes "csod_initial_state".
        """
        self.state.messages.append({"role": "user", "content": user_message})

        if self.state.phase == ConversationPhase.INITIAL:
            return await self._handle_initial(user_message)

        elif self.state.phase == ConversationPhase.INTENT_CONFIRM:
            return await self._handle_intent_confirm(user_message)

        elif self.state.phase == ConversationPhase.SCOPING:
            return await self._handle_scoping(user_message)

        elif self.state.phase == ConversationPhase.METRIC_BUILD:
            return await self._handle_metric_build_confirm(user_message)

        return {"phase": "unknown", "message": "I didn't understand that. Can you rephrase?"}

    # ── Phase handlers ────────────────────────────────────────────────────────

    async def _handle_initial(self, user_message: str) -> Dict[str, Any]:
        """Phase 1: Classify intent and confirm with user."""
        self.state.user_query = user_message
        
        result = await self._classify_intent(user_message)
        self.state.flow = LexyFlow(result["flow"].lower())
        
        # Build Phase 1 response
        flow_key = self.state.flow.value
        if flow_key in FLOW_CONFIRMATIONS:
            conf = FLOW_CONFIRMATIONS[flow_key]
            message = conf["message"]
            options = conf["options"]
        else:
            message = result.get("confirmation_message", "Can you tell me more about what you're trying to understand?")
            options = result.get("confirmation_options", ["Yes, that's right", "Not quite"])

        self.state.phase = ConversationPhase.INTENT_CONFIRM
        self.state.messages.append({"role": "assistant", "content": message})

        return {
            "phase": "intent_confirm",
            "flow": self.state.flow.value,
            "message": message,
            "options": options,
        }

    async def _handle_intent_confirm(self, user_message: str) -> Dict[str, Any]:
        """User confirmed (or redirected) the use case. Move to scoping."""
        # Detect redirect (e.g. "just a list of overdue employees")
        redirect = self._detect_simple_redirect(user_message)
        if redirect:
            return await self._handle_simple_redirect(redirect)

        # Load scoping questions for this flow
        flow_key = self.state.flow.value
        self._scoping_queue = list(SCOPING_QUESTIONS.get(flow_key, []))
        
        self.state.phase = ConversationPhase.SCOPING
        return await self._present_next_scoping_questions()

    async def _handle_scoping(self, user_message: str) -> Dict[str, Any]:
        """Process a scoping answer and either ask more or move to Phase 3."""
        self._parse_scoping_answer(user_message)

        if self._scoping_queue:
            return await self._present_next_scoping_questions()
        else:
            # All scoping done — resolve project then build metric narration
            return await self._build_metric_narration()

    async def _build_metric_narration(self) -> Dict[str, Any]:
        """Phase 3: Resolve project ID, generate metric narration."""
        # Resolve project
        match = select_project(
            flow=self.state.flow,
            scoping=self.state.scoping,
            data_sources=["cornerstone"],  # TODO: from user session/tenant
        )
        self.state.active_project_id = match.project_id
        self.state.selected_data_sources = match.data_sources
        self.state.project_selector_confidence = match.confidence

        # Generate narration
        narration_result = await self._generate_metric_narration()
        self.state.metric_narration = narration_result.get("narration_text", "")
        
        self.state.phase = ConversationPhase.METRIC_BUILD
        self.state.messages.append({"role": "assistant", "content": self.state.metric_narration})

        return {
            "phase": "metric_build",
            "message": self.state.metric_narration,
            "options": narration_result.get("confirmation_options", [
                "This sounds right — show me the dashboard",
                "Add comparison to last year",
                "Narrow to a specific group",
            ]),
            "project_id": self.state.active_project_id,
        }

    async def _handle_metric_build_confirm(self, user_message: str) -> Dict[str, Any]:
        """User confirmed metric set. Build CSOD initial state and return it."""
        self._parse_metric_confirm_modifiers(user_message)

        self.state.phase = ConversationPhase.CONFIRMED
        csod_intent = self._resolve_csod_intent()
        self.state.csod_intent = csod_intent

        initial_state = build_csod_initial_state(self.state)

        return {
            "phase": "confirmed",
            "message": "Great — pulling the data together now. Your dashboard will be ready in a moment.",
            "csod_initial_state": initial_state,
            "use_advisor_workflow": self.state.use_advisor_workflow,
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _classify_intent(self, user_message: str) -> Dict[str, Any]:
        """LLM call to classify the opening question into a LexyFlow."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=INTENT_CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"flow": "UNKNOWN", "confidence": 0.0, "confirmation_message": text, "confirmation_options": []}

    async def _present_next_scoping_questions(self) -> Dict[str, Any]:
        """Pull up to 3 questions from the queue and present them."""
        batch = self._scoping_queue[:3]
        self._scoping_queue = self._scoping_queue[3:]

        flow_key = self.state.flow.value
        intro = SCOPING_INTRO.get(flow_key, "A few quick questions:")

        return {
            "phase": "scoping",
            "message": intro,
            "questions": [
                {"id": q["id"], "text": q["question"], "options": q["options"]}
                for q in batch
            ],
        }

    def _parse_scoping_answer(self, user_message: str):
        """
        Map user answer text back to state fields.
        In production this is a small LLM call or option-index matching.
        Stub: tries to match user_message against known option values.
        """
        flow_key = self.state.flow.value
        all_questions = SCOPING_QUESTIONS.get(flow_key, [])
        for q in all_questions:
            for idx, opt in enumerate(q.get("options", [])):
                if opt.lower() in user_message.lower():
                    values = q.get("option_values", [])
                    if idx < len(values):
                        setattr(self.state.scoping, q["state_key"], values[idx])
                    break

    async def _generate_metric_narration(self) -> Dict[str, Any]:
        """LLM call to generate Phase 3 metric narration."""
        prompt = METRIC_BUILD_SYSTEM.format(
            flow=self.state.flow.value,
            scoping_json=self.state.scoping.model_dump_json(indent=2),
            project_name=self.state.active_project_id,
            data_sources=", ".join(self.state.selected_data_sources),
        )
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=800,
            system=prompt,
            messages=[{"role": "user", "content": "Generate the metric narration now."}],
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

    def _resolve_csod_intent(self) -> str:
        FLOW_TO_INTENT = {
            LexyFlow.COMPLIANCE_RISK: "metrics_dashboard_plan",
            LexyFlow.SKILLS_GAP: "metrics_recommender_with_gold_plan",
            LexyFlow.LEARNING_EFFECTIVENESS: "dashboard_generation_for_persona",
            LexyFlow.TRAINING_ROI: "metrics_dashboard_plan",
            LexyFlow.METRIC_ADVISOR: "metric_kpi_advisor",
        }
        intent = FLOW_TO_INTENT.get(self.state.flow, "metrics_dashboard_plan")
        if intent == "metric_kpi_advisor":
            self.state.use_advisor_workflow = True
        return intent

    def _detect_simple_redirect(self, user_message: str) -> Optional[str]:
        REDIRECTS = {
            "just a list": "simple_list",
            "overdue employees": "simple_list",
            "skills inventory": "simple_report",
        }
        msg_lower = user_message.lower()
        for trigger, redirect_type in REDIRECTS.items():
            if trigger in msg_lower:
                return redirect_type
        return None

    async def _handle_simple_redirect(self, redirect_type: str) -> Dict[str, Any]:
        self.state.phase = ConversationPhase.CONFIRMED
        self.state.csod_intent = "metrics_dashboard_plan"
        initial_state = build_csod_initial_state(self.state)
        return {
            "phase": "confirmed",
            "message": "Got it — pulling a filtered view together now.",
            "csod_initial_state": initial_state,
            "use_advisor_workflow": False,
        }

    def _parse_metric_confirm_modifiers(self, user_message: str):
        """Detect modifiers like 'add last year comparison' or 'narrow to a group'."""
        msg_lower = user_message.lower()
        if "last year" in msg_lower or "comparison" in msg_lower:
            self.state.scoping.time_window = "yoy"
```

---

## 8. Workflow Bridge — `workflow_bridge.py`

```python
"""
WorkflowBridge

Converts a completed ConversationState into the correct initial_state dict
for either csod_workflow or csod_metric_advisor_workflow.
"""
from app.agents.lexy.conversation_state import ConversationState, LexyFlow
from app.agents.csod.csod_workflow import create_csod_initial_state
from app.agents.csod.csod_metric_advisor_workflow import create_csod_metric_advisor_initial_state


def build_csod_initial_state(state: ConversationState) -> dict:
    """
    Build the correct CSOD initial state from a completed ConversationState.
    Routes to advisor workflow when flow == METRIC_ADVISOR.
    """
    # Map time window to compliance profile
    time_window = state.scoping.time_window or "last_quarter"
    org_unit = state.scoping.org_unit or "whole_org"

    compliance_profile = {
        "time_window": time_window,
        "org_unit": org_unit,
        "org_unit_value": state.scoping.org_unit_value,
        "training_type": state.scoping.training_type,
        "onset_pattern": state.scoping.onset_pattern,
        "breadth": state.scoping.breadth,
        "persona": state.scoping.persona or _infer_persona(state),
        "cost_focus": state.scoping.cost_focus,
        "skills_domain": state.scoping.skills_domain,
        "flow": state.flow.value,
        # Pass metric narration as context for the CSOD nodes
        "lexy_metric_narration": state.metric_narration,
    }

    if state.use_advisor_workflow:
        return create_csod_metric_advisor_initial_state(
            user_query=state.user_query,
            session_id=state.session_id,
            active_project_id=state.active_project_id,
            selected_data_sources=state.selected_data_sources,
            compliance_profile=compliance_profile,
            causal_graph_enabled=True,
            causal_vertical="lms",
        )
    else:
        return create_csod_initial_state(
            user_query=state.user_query,
            session_id=state.session_id,
            active_project_id=state.active_project_id,
            selected_data_sources=state.selected_data_sources,
            compliance_profile=compliance_profile,
            causal_graph_enabled=state.causal_graph_enabled,
            causal_vertical="lms",
        )


def _infer_persona(state: ConversationState) -> str:
    """Infer persona from flow if not explicitly set."""
    FLOW_DEFAULT_PERSONA = {
        LexyFlow.COMPLIANCE_RISK: "compliance_officer",
        LexyFlow.SKILLS_GAP: "ld_manager",
        LexyFlow.LEARNING_EFFECTIVENESS: "ld_manager",
        LexyFlow.TRAINING_ROI: "chro",
        LexyFlow.METRIC_ADVISOR: "ld_manager",
    }
    return FLOW_DEFAULT_PERSONA.get(state.flow, "ld_manager")
```

---

## 9. Changes to Existing Files

### `csod_workflow.py` — Required changes

**Change 1:** Add `lexy_metric_narration` to `compliance_profile` consumption in `csod_intent_classifier_node`. When `compliance_profile.get("lexy_metric_narration")` is present, the intent classifier should **skip LLM classification** and use the pre-resolved intent directly. The conversational layer already did the classification.

```python
# In csod_intent_classifier_node (csod_nodes.py):
def csod_intent_classifier_node(state):
    # Check if conversation layer already resolved intent
    profile = state.get("compliance_profile", {})
    lexy_narration = profile.get("lexy_metric_narration")
    if lexy_narration and state.get("csod_intent"):
        # Intent pre-resolved by conversational layer — pass through
        logger.info(f"Intent pre-resolved by Lexy: {state['csod_intent']}")
        return state
    # ... existing LLM classification logic
```

**Change 2:** Pass `compliance_profile.time_window`, `org_unit`, and `persona` fields into the planner and metrics retrieval nodes as filter context. These replace the need for the planner to ask clarifying questions internally.

**No changes required** to routing logic, graph topology, or state schema.

---

### `csod_metric_advisor_workflow.py` — No changes required

The advisor workflow already accepts `active_project_id` and `compliance_profile` via `create_csod_metric_advisor_initial_state()`. The bridge handles the mapping.

---

## 10. API Endpoint — `api/routes/lexy_conversation.py`

```python
"""
POST /api/lexy/conversation
Stateful multi-turn conversation endpoint for Lexy.

Session state is held in Redis (or in-memory for dev) keyed by session_id.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/lexy", tags=["lexy"])

# In-memory session store for dev (replace with Redis in prod)
_sessions: dict = {}


class ConversationRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ConversationResponse(BaseModel):
    session_id: str
    phase: str
    message: str
    options: list = []
    questions: list = []
    csod_initial_state: Optional[dict] = None
    use_advisor_workflow: bool = False


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(req: ConversationRequest):
    from app.agents.lexy.conversational_orchestrator import LexyConversationalOrchestrator
    import uuid

    session_id = req.session_id or str(uuid.uuid4())

    if session_id not in _sessions:
        _sessions[session_id] = LexyConversationalOrchestrator(session_id=session_id)

    orchestrator = _sessions[session_id]
    result = await orchestrator.process_message(req.message)
    result["session_id"] = session_id

    # If confirmed, optionally kick off CSOD pipeline async here
    if result["phase"] == "confirmed":
        del _sessions[session_id]  # cleanup

    return result
```

---

## 11. Implementation Sequence for Cursor

Execute in this order. Each step is independently testable before moving to the next.

### Step 1 — Data models and project selector
**Files:** `conversation_state.py`, `project_selector_tool.py`  
**Test:** Unit test `select_project()` for all 5 flows with dummy registry.

### Step 2 — Prompts layer
**Files:** All files under `prompts/`  
**Test:** Render each prompt template with sample values, verify no broken format strings.

### Step 3 — Workflow bridge
**Files:** `workflow_bridge.py`  
**Test:** Build a mock `ConversationState` for each flow and verify the output state dict has correct `csod_intent`, `active_project_id`, and `compliance_profile` keys.

### Step 4 — Orchestrator core loop
**Files:** `conversational_orchestrator.py`  
**Test:** Step through all 5 flows end-to-end with mocked LLM responses. Assert correct phase transitions and final `csod_initial_state`.

### Step 5 — Intent classifier shortcut in csod_nodes
**Files:** `csod_nodes.py` (existing)  
**Change:** Add pre-resolved intent bypass (Section 9 above).  
**Test:** Invoke existing CSOD workflow with a state that has `csod_intent` pre-set + `lexy_metric_narration` populated. Confirm it skips re-classification.

### Step 6 — API endpoint
**Files:** `api/routes/lexy_conversation.py`  
**Test:** Integration test using curl/httpx — simulate a full 5-turn conversation per flow and assert `phase == "confirmed"` returns a valid `csod_initial_state`.

### Step 7 — Session persistence (Redis)
**Files:** `api/routes/lexy_conversation.py` (update)  
**Change:** Swap `_sessions` dict for Redis-backed session store with TTL.  
**Test:** Simulate concurrent sessions, verify no cross-session state bleed.

---

## 12. Open Decisions

| Decision | Options | Recommendation |
|---|---|---|
| Scoping answer parsing | LLM call vs. option index matching | **Option index** for speed; LLM fallback for free-text responses |
| Phase 3 metric narration | LLM-generated vs. template-substituted | **Template first** (predictable, fast); LLM enrichment for advisor flow only |
| Session store | In-memory vs. Redis | **Redis** for production; in-memory stub is fine through Step 6 |
| ProjectSelector backend | Dummy registry vs. DB query | **Dummy registry** with exact interface as above; DB implementation drops in without changing orchestrator |
| Phase 4 (dashboard narration) | Generated by orchestrator vs. returned from CSOD assembler | **CSOD assembler** generates the narrative; orchestrator only streams it through — no prompt needed in orchestrator for Phase 4 |
