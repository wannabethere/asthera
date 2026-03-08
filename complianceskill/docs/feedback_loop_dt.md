# Dashboard Feedback Loop & User Input System — Design Document

## Overview

Two interlocking systems:

1. **Feedback Loop** — passively collects signals after dashboards are rendered, aggregates them into score adjustments, and propagates improvements back into the decision tree, template registry, and vector store.
2. **User Input System** — actively captures explicit corrections and preferences during and after dashboard generation, converting them into high-confidence training signal.

Both systems write to the same Postgres tables and feed the same re-ranking pipeline. Neither requires retraining a model — all improvements are score-weight adjustments and metadata enrichment applied at retrieval and scoring time.

---

## System Architecture

```
User Interaction
      │
      ├── Implicit signals          ── FeedbackCollector
      │   (view time, drill-downs,      └─► feedback_events table
      │    export, share, return)
      │
      └── Explicit signals          ── UserInputProcessor
          (thumbs, corrections,         └─► feedback_events table
           preference edits,                feedback_corrections table
           free-text)                       user_preferences table

                    │
                    ▼
            FeedbackAggregator          (runs on schedule or trigger)
            ├── aggregates raw events → feedback_scores table
            ├── detects drift patterns → drift_signals table
            └── emits WeightUpdateEvent

                    │
                    ▼
            FeedbackApplicator
            ├── TemplateScoreAdjuster   → updates template_score_overrides table
            ├── DecisionWeightUpdater   → updates decision_weight_overrides table
            └── VectorStoreReIndexer    → re-embeds templates with boosted text
```

---

## Part 1 — Feedback Loop

### 1.1 Data Models

```python
# app/feedback/models.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class FeedbackSignalType(str, Enum):
    # Implicit
    VIEW_DURATION        = "view_duration"        # seconds spent on dashboard
    PANEL_CLICK          = "panel_click"          # user clicked into a panel
    DRILL_DOWN           = "drill_down"           # used drill-down interaction
    EXPORT               = "export"               # exported to PDF/CSV
    SHARE                = "share"                # shared dashboard link
    RETURN_VISIT         = "return_visit"         # reopened same dashboard spec
    FILTER_APPLIED       = "filter_applied"       # used a filter chip
    # Explicit
    THUMBS_UP            = "thumbs_up"
    THUMBS_DOWN          = "thumbs_down"
    STAR_RATING          = "star_rating"          # 1–5
    TEMPLATE_SWAP        = "template_swap"        # user picked a different template
    METRIC_REMOVED       = "metric_removed"       # user removed a metric from strip
    METRIC_ADDED         = "metric_added"         # user added a metric not suggested
    PANEL_REORDERED      = "panel_reordered"      # user reordered panels
    DESTINATION_CHANGED  = "destination_changed"  # user switched destination type
    FREE_TEXT            = "free_text"            # open comment
    DECISION_CORRECTION  = "decision_correction"  # user corrected a resolved decision


@dataclass
class FeedbackEvent:
    """
    One feedback signal emitted by the frontend or captured by a node.
    Written to feedback_events table.
    """
    session_id:       str
    group_id:         str                   # artifact group that was rendered
    template_id:      str                   # winning template that was shown
    signal_type:      FeedbackSignalType
    value:            Any                   # numeric for duration/rating; str for text
    resolved_decisions: Dict[str, str]      # snapshot of decisions at render time
    user_id:          Optional[str] = None
    tenant_id:        Optional[str] = None
    destination_type: Optional[str] = None
    panel_id:         Optional[str] = None  # which panel if panel-level signal
    metric_id:        Optional[str] = None  # which metric if metric-level signal
    timestamp:        datetime = field(default_factory=datetime.utcnow)
    metadata:         Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackCorrection:
    """
    Explicit user correction to a resolved decision or metric selection.
    Written to feedback_corrections table.
    High-confidence training signal — weighted 5× vs implicit signals.
    """
    session_id:       str
    group_id:         str
    field_corrected:  str        # "category" | "focus_area" | "template_id" | "metric_id" etc.
    original_value:   str
    corrected_value:  str
    confidence:       float = 1.0
    user_id:          Optional[str] = None
    tenant_id:        Optional[str] = None
    timestamp:        datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserPreference:
    """
    Persistent user or tenant preference.
    Written to user_preferences table.
    Applied as a hard constraint (not a soft score boost) in the decision tree.
    """
    scope:        str        # "user" | "tenant" | "group"
    scope_id:     str        # user_id | tenant_id | group_id
    preference_key:   str    # see PreferenceKey enum below
    preference_value: Any
    set_at:       datetime = field(default_factory=datetime.utcnow)


class PreferenceKey(str, Enum):
    DEFAULT_DESTINATION  = "default_destination"   # "embedded" | "powerbi" etc.
    DEFAULT_COMPLEXITY   = "default_complexity"     # "low" | "medium" | "high"
    DEFAULT_THEME        = "default_theme"          # "light" | "dark"
    PREFERRED_CHART_TYPES= "preferred_chart_types"  # list of chart type ids
    EXCLUDED_TEMPLATES   = "excluded_templates"     # list of template_ids to never show
    PINNED_METRICS       = "pinned_metrics"         # list of metric_ids always included
    EXCLUDED_METRICS     = "excluded_metrics"       # list of metric_ids never included
    PREFERRED_AUDIENCE   = "preferred_audience"     # overrides resolved audience
```

---

### 1.2 Postgres Schema

```sql
-- feedback_events
-- One row per signal. Append-only. Never updated.
CREATE TABLE feedback_events (
    id                  BIGSERIAL       PRIMARY KEY,
    session_id          VARCHAR(120)    NOT NULL,
    group_id            VARCHAR(120)    NOT NULL,
    template_id         VARCHAR(120)    NOT NULL,
    signal_type         VARCHAR(60)     NOT NULL,
    value               JSONB,                          -- numeric | string | null
    resolved_decisions  JSONB           NOT NULL,       -- snapshot
    destination_type    VARCHAR(40),
    panel_id            VARCHAR(120),
    metric_id           VARCHAR(200),
    user_id             VARCHAR(120),
    tenant_id           VARCHAR(120),
    timestamp           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    metadata            JSONB           DEFAULT '{}'
);

CREATE INDEX idx_fe_group        ON feedback_events(group_id);
CREATE INDEX idx_fe_template     ON feedback_events(template_id);
CREATE INDEX idx_fe_signal_type  ON feedback_events(signal_type);
CREATE INDEX idx_fe_tenant       ON feedback_events(tenant_id);
CREATE INDEX idx_fe_timestamp    ON feedback_events(timestamp DESC);

-- feedback_corrections
-- Explicit user corrections. Highest-weight training signal.
CREATE TABLE feedback_corrections (
    id               BIGSERIAL      PRIMARY KEY,
    session_id       VARCHAR(120)   NOT NULL,
    group_id         VARCHAR(120)   NOT NULL,
    field_corrected  VARCHAR(80)    NOT NULL,
    original_value   VARCHAR(200)   NOT NULL,
    corrected_value  VARCHAR(200)   NOT NULL,
    confidence       NUMERIC(4,3)   NOT NULL DEFAULT 1.0,
    user_id          VARCHAR(120),
    tenant_id        VARCHAR(120),
    timestamp        TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fc_field         ON feedback_corrections(field_corrected);
CREATE INDEX idx_fc_original      ON feedback_corrections(original_value);
CREATE INDEX idx_fc_corrected     ON feedback_corrections(corrected_value);

-- user_preferences
-- Persistent hard constraints. Upsert-on-scope+key.
CREATE TABLE user_preferences (
    id                BIGSERIAL      PRIMARY KEY,
    scope             VARCHAR(20)    NOT NULL,      -- user | tenant | group
    scope_id          VARCHAR(120)   NOT NULL,
    preference_key    VARCHAR(80)    NOT NULL,
    preference_value  JSONB          NOT NULL,
    set_at            TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (scope, scope_id, preference_key)
);

-- feedback_scores
-- Aggregated scores per (template_id, decision_context_hash).
-- Written by FeedbackAggregator. Read by TemplateScoreAdjuster.
CREATE TABLE feedback_scores (
    template_id             VARCHAR(120)    NOT NULL,
    decision_context_hash   VARCHAR(32)     NOT NULL,   -- hash of category+focus+audience+dest
    destination_type        VARCHAR(40)     NOT NULL,
    positive_count          INT             NOT NULL DEFAULT 0,
    negative_count          INT             NOT NULL DEFAULT 0,
    correction_count        INT             NOT NULL DEFAULT 0,
    swap_away_count         INT             NOT NULL DEFAULT 0,   -- user switched away from this
    avg_view_duration_s     NUMERIC(8,2),
    weighted_score          NUMERIC(6,4)    NOT NULL DEFAULT 0.5, -- 0.0–1.0
    sample_count            INT             NOT NULL DEFAULT 0,
    last_updated            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (template_id, decision_context_hash)
);

-- template_score_overrides
-- Delta adjustments applied on top of deterministic scores at scoring time.
-- Written by TemplateScoreAdjuster. Read by _score_template().
CREATE TABLE template_score_overrides (
    template_id       VARCHAR(120)    NOT NULL,
    context_hash      VARCHAR(32)     NOT NULL,
    score_delta       NUMERIC(5,4)    NOT NULL DEFAULT 0.0,  -- added to composite_score
    boost_reason      VARCHAR(200),
    confidence        NUMERIC(4,3)    NOT NULL DEFAULT 0.5,
    valid_until       TIMESTAMPTZ,                            -- null = permanent
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (template_id, context_hash)
);

-- decision_weight_overrides
-- Per-question weight adjustments for the scoring formula.
-- Normally weights are hardcoded (category=30, focus=20, etc.).
-- This table allows gradual drift toward data-driven weights.
CREATE TABLE decision_weight_overrides (
    question_key      VARCHAR(80)     NOT NULL,
    option_id         VARCHAR(80)     NOT NULL,
    weight_delta      NUMERIC(6,3)    NOT NULL DEFAULT 0.0,
    sample_count      INT             NOT NULL DEFAULT 0,
    last_updated      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (question_key, option_id)
);

-- drift_signals
-- Detected patterns where the current resolution is diverging from user corrections.
CREATE TABLE drift_signals (
    id                BIGSERIAL       PRIMARY KEY,
    question_key      VARCHAR(80)     NOT NULL,
    from_option       VARCHAR(80)     NOT NULL,    -- what the system resolved
    to_option         VARCHAR(80)     NOT NULL,    -- what users corrected to
    correction_count  INT             NOT NULL,
    period_start      TIMESTAMPTZ     NOT NULL,
    period_end        TIMESTAMPTZ     NOT NULL,
    drift_score       NUMERIC(5,4),               -- 0=no drift, 1=always wrong
    acknowledged      BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

---

### 1.3 FeedbackCollector

```python
# app/feedback/collector.py

class FeedbackCollector:
    """
    Entry point for all feedback writes. Called by:
      - Frontend via POST /api/feedback (implicit + explicit events)
      - LangGraph nodes (post-render node writes initial VIEW event)
      - Interactive node (writes DECISION_CORRECTION on user response)

    Methods are fire-and-forget — they enqueue to an async writer,
    never block the rendering pipeline.
    """

    def __init__(self, db_writer: FeedbackDBWriter, queue_size: int = 1000):
        ...

    def record(self, event: FeedbackEvent) -> None:
        """
        Enqueue one FeedbackEvent for async DB write.
        Never raises — silently drops if queue is full and logs warning.
        """
        ...

    def record_correction(self, correction: FeedbackCorrection) -> None:
        """
        Enqueue a high-confidence correction.
        Corrections bypass the queue and write synchronously.
        """
        ...

    def record_preference(self, preference: UserPreference) -> None:
        """
        Upsert a persistent user/tenant preference.
        Writes synchronously — preferences are load-bearing for the next request.
        """
        ...

    def from_interactive_response(
        self,
        session_id: str,
        group_id: str,
        original_decisions: Dict[str, str],
        user_response: Dict[str, str],      # {question_key: corrected_option_id}
        template_id: str,
    ) -> None:
        """
        Convenience: emit one DECISION_CORRECTION event per corrected key.
        Called by dt_dashboard_decision_interactive_node after merging user answers.
        """
        for key, corrected_val in user_response.items():
            original_val = original_decisions.get(key, "")
            if original_val != corrected_val:
                self.record_correction(FeedbackCorrection(
                    session_id=session_id,
                    group_id=group_id,
                    field_corrected=key,
                    original_value=original_val,
                    corrected_value=corrected_val,
                ))
```

---

### 1.4 FeedbackAggregator

```python
# app/feedback/aggregator.py

class FeedbackAggregator:
    """
    Runs on a schedule (e.g., every 15 minutes via n8n cron trigger,
    or triggered by FeedbackCollector when correction_count crosses threshold).

    Reads feedback_events + feedback_corrections, writes:
      - feedback_scores (per template × context)
      - drift_signals (when correction pattern exceeds drift_threshold)
      - Emits WeightUpdateEvent to FeedbackApplicator
    """

    # Weights for computing weighted_score
    SIGNAL_WEIGHTS = {
        FeedbackSignalType.THUMBS_UP:          +1.0,
        FeedbackSignalType.THUMBS_DOWN:        -1.0,
        FeedbackSignalType.STAR_RATING:         None,   # normalised: (rating-1)/4 * 2 - 1
        FeedbackSignalType.TEMPLATE_SWAP:      -0.8,   # user chose a different template
        FeedbackSignalType.DRILL_DOWN:         +0.3,   # engagement signal
        FeedbackSignalType.EXPORT:             +0.4,
        FeedbackSignalType.SHARE:              +0.5,
        FeedbackSignalType.RETURN_VISIT:       +0.6,
        FeedbackSignalType.VIEW_DURATION:       None,   # normalised against median
        FeedbackSignalType.DECISION_CORRECTION:-0.5,   # system got a decision wrong
    }

    CORRECTION_WEIGHT_MULTIPLIER = 5.0   # corrections count 5× vs implicit signals
    DRIFT_THRESHOLD = 0.65               # if correction rate for a decision > 65%, emit drift signal

    def __init__(self, db: FeedbackDB, applicator: "FeedbackApplicator"):
        ...

    def run(self, lookback_hours: int = 24) -> AggregationResult:
        """
        Main entry point. Reads events from the last lookback_hours window,
        updates feedback_scores, detects drift, emits weight updates.
        """
        ...

    def _compute_weighted_score(
        self,
        events: List[FeedbackEvent],
        corrections: List[FeedbackCorrection],
    ) -> float:
        """
        Compute a single 0.0–1.0 score for a (template, context) pair.
        Formula:
          raw = Σ(signal_weight × event_weight) / total_weight
          correction_penalty = correction_count × CORRECTION_WEIGHT_MULTIPLIER × -0.5
          score = clamp(0.5 + raw + correction_penalty, 0.0, 1.0)
        """
        ...

    def _detect_drift(
        self,
        corrections: List[FeedbackCorrection],
        period_start: datetime,
        period_end: datetime,
    ) -> List[DriftSignal]:
        """
        Group corrections by (field_corrected, original_value, corrected_value).
        If any group has correction_rate > DRIFT_THRESHOLD, emit a DriftSignal.

        DriftSignal means: "for this question, when the system resolves option A,
        users correct it to option B more than 65% of the time."
        This is the signal that the LLM prompt or keyword fallback has a systematic
        error for a specific case.
        """
        ...


@dataclass
class AggregationResult:
    scores_updated:    int
    drift_signals:     List[DriftSignal]
    weight_updates:    List[WeightUpdate]
    period_start:      datetime
    period_end:        datetime


@dataclass
class DriftSignal:
    question_key:     str
    from_option:      str
    to_option:        str
    correction_count: int
    drift_score:      float
    # Actionable recommendation generated alongside the signal:
    recommendation:   str   # e.g. "Add keyword 'csod' to learning_development option"


@dataclass
class WeightUpdate:
    template_id:     str
    context_hash:    str
    score_delta:     float    # how much to shift composite_score for this (template, context)
    reason:          str
    confidence:      float
```

---

### 1.5 FeedbackApplicator

```python
# app/feedback/applicator.py

class FeedbackApplicator:
    """
    Applies aggregated feedback to the three layers where it has effect:

    Layer 1 — TemplateScoreAdjuster
      Writes score_delta to template_score_overrides.
      _score_template() in dt_dashboard_decision_nodes.py reads this table
      and adds delta to composite_score before returning.

    Layer 2 — DecisionWeightUpdater
      Writes weight_delta to decision_weight_overrides.
      resolve_decisions() uses these to adjust the per-question point values
      in the scoring formula (currently hardcoded: category=30, focus=20, etc.).

    Layer 3 — VectorStoreReIndexer
      For templates with consistently high positive feedback, appends
      feedback-derived text to the embedding_text and re-indexes.
      This biases RETRIEVAL POINT 1 toward templates users actually prefer.
    """

    def __init__(
        self,
        db: FeedbackDB,
        vector_writer: "VectorStoreWriter",   # from ingest/vector_writer.py
    ):
        ...

    def apply(self, updates: List[WeightUpdate]) -> ApplicatorResult:
        """
        Apply all pending weight updates atomically.
        Called by FeedbackAggregator.run() after scores are computed.
        """
        ...

    class TemplateScoreAdjuster:
        """
        Reads feedback_scores, computes score_delta, upserts template_score_overrides.

        score_delta formula:
          delta = (weighted_score - 0.5) × 0.15
          # Max delta is ±0.075 — caps at 6.5% of the 115-point raw max
          # Prevents feedback from completely overriding structural scores

        Applied in _score_template():
          score += score_override_delta  # added after normalisation
        """
        def update(self, scores: List[FeedbackScore]) -> int:
            """Returns number of overrides written."""
            ...

    class DecisionWeightUpdater:
        """
        Reads drift_signals, adjusts question weights in decision_weight_overrides.

        If drift is detected (e.g., category=security_ops is corrected to
        learning_development 70% of the time when data_sources contains "cornerstone"):

        1. Increase the weight given to source_capability signals in _resolve_from_state_fallback
           by writing a weight_delta for that keyword pattern.
        2. Log a human-readable recommendation for a prompt update.

        Note: This does NOT auto-update the LLM prompt. It writes a recommendation
        to drift_signals.recommendation for a human to review. Prompt updates are
        manual — automated prompt mutation is too risky.
        """
        def update(self, drift_signals: List[DriftSignal]) -> int:
            ...

    class VectorStoreReIndexer:
        """
        For templates where weighted_score > 0.75 AND sample_count > 20,
        appends feedback keywords to embedding_text and re-indexes.

        Example: training-plan-tracker has high positive feedback for queries
        containing "cornerstone" + "overdue assignments".
        Appended text: "cornerstone overdue assignments training completion feedback:positive"

        This shifts semantic retrieval toward this template for similar queries.
        The boost is proportional to weighted_score and capped at +200 chars.
        """
        REINDEX_THRESHOLD_SCORE  = 0.75
        REINDEX_THRESHOLD_SAMPLE = 20

        def reindex_high_performers(
            self,
            scores: List[FeedbackScore],
            templates: List[Dict],
        ) -> int:
            """Returns number of templates re-indexed."""
            ...
```

---

## Part 2 — User Input System

### 2.1 Overview

Three input channels, each converting user intent into one of: a `FeedbackCorrection`, a `UserPreference`, or a direct state mutation that the decision node picks up on the next run.

```
Channel 1: Inline correction widget  (rendered alongside dashboard)
  → FeedbackCorrection + immediate re-render with corrected decisions

Channel 2: Preference panel  (persistent settings UI)
  → UserPreference → applied as hard constraint on all future requests

Channel 3: Conversational refinement  (free-text chat, post-render)
  → UserInputProcessor.parse() → structured correction/preference/re-run request
```

---

### 2.2 UserInputProcessor

```python
# app/feedback/user_input_processor.py

class UserInputProcessor:
    """
    Converts raw user input (free text, widget responses, preference changes)
    into structured corrections and preferences.

    Single entry point for all three input channels.
    Called by the API layer — not a LangGraph node itself, but emits
    state mutations that the next graph run picks up.
    """

    def __init__(
        self,
        collector: FeedbackCollector,
        llm_parser: "UserInputLLMParser",
    ):
        ...

    def process_widget_response(
        self,
        session_id: str,
        group_id: str,
        field: str,
        original_value: str,
        corrected_value: str,
        user_id: Optional[str] = None,
    ) -> UserInputResult:
        """
        Handle a correction from the inline correction widget.
        Validates corrected_value against VALID_OPTIONS, records correction,
        returns a StateOverride for the re-render.
        """
        ...

    def process_preference_change(
        self,
        scope: str,
        scope_id: str,
        key: PreferenceKey,
        value: Any,
    ) -> UserInputResult:
        """
        Upsert a persistent preference.
        Also emits a FeedbackEvent so the aggregator can weight it.
        """
        ...

    def process_free_text(
        self,
        session_id: str,
        group_id: str,
        text: str,
        current_decisions: Dict[str, str],
        current_template_id: str,
        user_id: Optional[str] = None,
    ) -> UserInputResult:
        """
        Parse free-text feedback into structured actions.
        Calls UserInputLLMParser.parse() then routes to correction/preference/re-run.

        Examples:
          "This should be for my compliance team not the SOC" →
            FeedbackCorrection(field="audience", original="soc_analyst", corrected="compliance_team")

          "Always use dark theme for our team" →
            UserPreference(scope="tenant", key="default_theme", value="dark")

          "Can you show this in Power BI format?" →
            StateOverride(destination_type="powerbi") + re-render trigger

          "Add training overdue rate to the strip" →
            PinnedMetricRequest(metric_hint="training overdue rate")
        """
        ...


@dataclass
class UserInputResult:
    """Returned from all UserInputProcessor methods."""
    action_type:     str                  # "correction" | "preference" | "re_render" | "no_op"
    corrections:     List[FeedbackCorrection] = field(default_factory=list)
    preferences:     List[UserPreference]     = field(default_factory=list)
    state_overrides: Dict[str, Any]           = field(default_factory=dict)  # merged into state for re-render
    re_render:       bool                     = False
    message:         str                      = ""   # human-readable confirmation


class UserInputLLMParser:
    """
    LLM call that converts free-text user feedback into structured actions.
    Uses prompt: 19_parse_user_feedback.md

    Input to LLM:
      {
        "user_text": "...",
        "current_decisions": {...},
        "current_template_id": "...",
        "valid_options": VALID_OPTIONS,   # from dashboard_decision_tree.py
      }

    Expected LLM output:
      {
        "action_type": "correction" | "preference" | "re_render" | "metric_pin" | "no_op",
        "corrections": [{"field": "...", "corrected_value": "..."}],
        "preferences": [{"key": "...", "value": "..."}],
        "state_overrides": {"destination_type": "powerbi"},
        "metric_hints": ["training overdue rate"],
        "confidence": 0.0–1.0,
        "message": "..."
      }

    Falls back to "no_op" if LLM fails or confidence < 0.5.
    """

    def parse(
        self,
        user_text: str,
        current_decisions: Dict[str, str],
        current_template_id: str,
    ) -> ParsedUserInput:
        ...


@dataclass
class ParsedUserInput:
    action_type:     str
    corrections:     List[Dict]     = field(default_factory=list)
    preferences:     List[Dict]     = field(default_factory=list)
    state_overrides: Dict[str, Any] = field(default_factory=dict)
    metric_hints:    List[str]      = field(default_factory=list)
    confidence:      float          = 0.0
    message:         str            = ""
```

---

### 2.3 PreferenceLoader

```python
# app/feedback/preference_loader.py

class PreferenceLoader:
    """
    Loads active preferences for a user/tenant at the start of each pipeline run
    and injects them into state as hard constraints.

    Called by the retrieve_context node BEFORE the decision node runs,
    so preferences override resolved decisions, not the other way around.

    State fields written:
        user_preference_overrides   — {question_key: option_id} hard constraints
        pinned_metrics              — [metric_id, ...] always include
        excluded_metrics            — [metric_id, ...] never include
        excluded_templates          — [template_id, ...] removed before scoring
    """

    def __init__(self, db: FeedbackDB):
        ...

    def load_for_state(
        self,
        state: Dict[str, Any],
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns state additions. Merge into state before decision node runs:
            state.update(loader.load_for_state(state, user_id, tenant_id))
        """
        ...

    def _preference_to_state_field(self, pref: UserPreference) -> Dict[str, Any]:
        """
        Maps PreferenceKey to the state field it constrains.

        DEFAULT_DESTINATION  → state["output_format"]     (hard override)
        DEFAULT_COMPLEXITY   → state["user_preference_overrides"]["complexity"]
        EXCLUDED_TEMPLATES   → state["excluded_templates"] (removes from dt_enriched_templates)
        PINNED_METRICS       → state["pinned_metrics"]     (forces into strip_kpis)
        PREFERRED_AUDIENCE   → state["user_preference_overrides"]["audience"]
        """
        ...
```

---

### 2.4 StateOverrideApplicator

```python
# app/feedback/state_override_applicator.py

class StateOverrideApplicator:
    """
    Merges UserInputResult.state_overrides and loaded preferences
    into state before the decision node runs.

    Designed to be called as a LangGraph node:

        graph.add_node("apply_overrides", StateOverrideApplicator().as_node)
        graph.add_edge("retrieve_context", "apply_overrides")
        graph.add_edge("apply_overrides", "dt_dashboard_decision_node")

    Hard constraints applied here take precedence over LLM resolution.
    Soft constraints (score boosts from feedback) are applied inside
    _score_template() using template_score_overrides.
    """

    def __init__(
        self,
        preference_loader: PreferenceLoader,
        score_override_reader: "ScoreOverrideReader",
    ):
        ...

    def as_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph-compatible node function."""
        user_id   = state.get("user_id")
        tenant_id = state.get("tenant_id")

        # 1. Load persistent preferences
        pref_overrides = self.preference_loader.load_for_state(
            state, user_id, tenant_id
        )

        # 2. Apply any session-level overrides from UserInputProcessor
        session_overrides = state.get("session_state_overrides", {})

        # 3. Load score overrides for templates in state
        template_ids = [
            t.get("template_id")
            for t in state.get("dt_enriched_templates", [])
        ]
        score_overrides = self.score_override_reader.load(
            template_ids=template_ids,
            context_hash=_build_context_hash(state),
        )

        # 4. Remove excluded templates
        excluded = pref_overrides.get("excluded_templates", [])
        if excluded:
            state["dt_enriched_templates"] = [
                t for t in state.get("dt_enriched_templates", [])
                if t.get("template_id") not in excluded
            ]

        # 5. Write all overrides into state
        state.update(pref_overrides)
        state.update(session_overrides)
        state["dt_retrieved_template_boosts"] = {
            **state.get("dt_retrieved_template_boosts", {}),
            **{tid: delta for tid, delta in score_overrides.items()},
        }

        return state


class ScoreOverrideReader:
    """
    Reads template_score_overrides from Postgres for a given
    (template_id list, context_hash) pair.
    Returns {template_id: score_delta} dict.
    """
    def load(
        self,
        template_ids: List[str],
        context_hash: str,
    ) -> Dict[str, float]:
        ...


def _build_context_hash(state: Dict[str, Any]) -> str:
    """
    Build a 16-char hash of the decision context for override lookup.
    Matches the hash used when scores were written by FeedbackAggregator.
    """
    import hashlib, json
    keys = ("category", "focus_area", "audience", "destination_type")
    decisions = state.get("dt_dashboard_decisions", {})
    payload = json.dumps({k: decisions.get(k, "") for k in keys}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
```

---

## Part 3 — Full Pipeline Integration

### 3.1 Updated Graph Topology

```
retrieve_context
      │
      ▼
apply_overrides          ← StateOverrideApplicator.as_node
  (loads preferences,        injects score boosts,
   removes excluded,         applies session overrides)
      │
      ▼
dt_dashboard_decision_node
  (resolves decisions,
   applies destination gate,
   scores templates + overrides,
   selects winner)
      │
  confidence < 0.6 AND interactive?
      │                  │
      │ yes              │ no
      ▼                  ▼
  interactive_node    spec_generation
      │
  user responds
      │
      ▼
  FeedbackCollector.from_interactive_response()
      │
      ▼
  spec_generation (re-run with updated decisions)
      │
      ▼
post_render_node         ← new node
  (emits VIEW event,
   writes session_id to state for frontend tracking)
```

### 3.2 post_render_node

```python
# app/agents/layout_advisor/nodes.py  (addition)

def post_render_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Emits the initial VIEW feedback event after a spec is committed.
    Called as the last node before END.

    This is the minimum feedback needed for the aggregator to have
    a denominator — without a VIEW event, we can't compute rates.
    """
    from app.feedback.collector import FeedbackCollector

    collector = FeedbackCollector.get_instance()
    collector.record(FeedbackEvent(
        session_id=state.get("session_id", ""),
        group_id=state.get("group_id", ""),
        template_id=(
            state.get("dt_winning_template", {}) or {}
        ).get("template_id", ""),
        signal_type=FeedbackSignalType.VIEW_DURATION,
        value=0,   # duration unknown at render time; updated by frontend later
        resolved_decisions=state.get("dt_dashboard_decisions", {}),
        destination_type=state.get("dt_dashboard_decisions", {}).get("destination_type"),
    ))
    return state
```

### 3.3 API Endpoints

```python
# app/api/feedback_router.py

# POST /api/feedback/event
# Body: FeedbackEvent (JSON)
# Called by frontend for implicit signals (duration, click, export)

# POST /api/feedback/correction
# Body: FeedbackCorrection (JSON)
# Called by inline correction widget

# PUT /api/feedback/preferences/{scope}/{scope_id}
# Body: {key: PreferenceKey, value: Any}
# Called by preference panel

# POST /api/feedback/free-text
# Body: {session_id, group_id, text, current_decisions, current_template_id}
# Returns: UserInputResult (with re_render flag and state_overrides)
# Called by the conversational chat panel post-render

# GET /api/feedback/drift-signals
# Returns: List[DriftSignal] for human review
# Called by an admin dashboard

# POST /api/feedback/drift-signals/{id}/acknowledge
# Marks a drift signal as reviewed + action taken
```

---

## Part 4 — Metric Feedback (parallel to dashboard)

The same four classes work for metrics with two additional signals:

```python
class MetricFeedbackSignalType(str, Enum):
    METRIC_KEPT       = "metric_kept"        # user accepted this metric in strip
    METRIC_REMOVED    = "metric_removed"     # user removed from strip
    METRIC_PROMOTED   = "metric_promoted"    # user moved to primary panel
    THRESHOLD_EDITED  = "threshold_edited"   # user changed warning/critical threshold
    CHART_TYPE_CHANGED= "chart_type_changed" # user changed chart type for this metric
    AXIS_LABEL_EDITED = "axis_label_edited"  # user edited the axis label
```

These write to the same `feedback_events` table with `metric_id` populated.

`FeedbackAggregator` detects:
- **Metrics consistently removed** for a given (focus_area, category) context → reduce their score in `metric_catalog` metadata
- **Threshold edits** → update `threshold_warning` / `threshold_critical` in `dashboard_metrics` table and re-index in vector store
- **Chart type changes** → update `chart_type` in `dashboard_metrics` and re-index

The `EnrichedMetric.embedding_text` already contains chart_type and thresholds, so a re-index is sufficient to propagate chart type corrections back to RETRIEVAL POINT 2.

---

## Part 5 — Drift Detection → Prompt Update Workflow

This is the highest-value output of the entire feedback system. When `drift_signals` accumulates a pattern, the recommended action is a prompt edit, not an automatic one.

```
drift_signals table
    ↓ (admin reviews via GET /api/feedback/drift-signals)
DriftSignal.recommendation field (human-readable text):
    "Users correct category=security_operations → learning_development
     65% of the time when data_sources contains 'cornerstone.lms'.
     Recommended: add 'cornerstone' as a keyword for learning_development
     in 18_resolve_dashboard_decisions.md OR strengthen the
     data_sources signal in _resolve_from_state_fallback."
    ↓
Human edits prompt or keyword map
    ↓
Re-run enricher (updates decision_tree.json + re-indexes decision_tree_options)
    ↓
Mark drift signal acknowledged
```

No automated prompt mutation. The system surfaces the pattern; a human makes the change. This keeps the feedback loop auditable and the prompt stable.

---

## Implementation Order

1. **Postgres schema** — create all 7 tables. No code dependencies.
2. **FeedbackEvent + FeedbackCorrection + UserPreference models** — pure dataclasses.
3. **FeedbackDBWriter** — simple INSERT/UPSERT wrapper, no business logic.
4. **FeedbackCollector** — enqueue + fire-and-forget pattern.
5. **post_render_node** — single node addition, wires collector into graph.
6. **ScoreOverrideReader + StateOverrideApplicator** — reads overrides, no aggregation needed yet. This gets you feedback-influenced scoring before the aggregator exists.
7. **PreferenceLoader + UserPreference API endpoint** — lets users set preferences immediately.
8. **UserInputLLMParser + UserInputProcessor + free-text API** — full conversational correction.
9. **FeedbackAggregator** — batch job. Wire to n8n cron or a simple APScheduler task.
10. **FeedbackApplicator (all three layers)** — completes the loop.
11. **Drift signal admin endpoint + review UI** — closes the human-in-the-loop on prompt updates.