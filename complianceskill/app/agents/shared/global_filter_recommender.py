"""
Global Filter Recommender
=========================

LLM layer that sits on top of the gold model builder output.  Given the
resolved MDL schemas, selected metrics/KPIs, and generated gold model SQL
it recommends a ``GlobalFilterConfig`` — a set of filter dimensions the
user can apply across every dashboard chart.

Called by:
  • csod_global_filter_configurator_node  (main workflow, after gold_sql)
  • POST /workflow/global_filter/recommend (standalone, after metrics selected)
  • POST /workflow/global_filter/refine    (follow-up Q&A to tighten criteria)

Example / instruction lookup is handled by ``FilterExampleProvider``.
Currently hardcoded; replace ``_load_examples`` / ``_load_instructions``
with vector-store retrieval when ready.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ===========================================================================
# Data models
# ===========================================================================

class FilterDimension(BaseModel):
    """One filterable dimension recommended for the dashboard."""
    id: str = Field(description="Machine-safe identifier, e.g. 'completion_date_range'")
    label: str = Field(description="Human-readable label shown in the UI")
    filter_type: str = Field(
        description="date_range | single_select | multi_select | numeric_range | boolean"
    )
    column: str = Field(description="Source column name")
    table: str = Field(description="Source table name")
    sql_fragment: str = Field(
        description="Parameterised WHERE clause snippet, e.g. "
                    "\"completion_date BETWEEN :start_date AND :end_date\""
    )
    operator: str = Field(description="SQL operator: BETWEEN | IN | = | >= | <=")
    default_value: Optional[Any] = Field(
        default=None,
        description="Sensible default: null (no filter), date string, list, etc."
    )
    applies_to: List[str] = Field(
        default_factory=lambda: ["all"],
        description="Metric/KPI names this filter affects, or ['all']"
    )
    is_global: bool = Field(
        default=True,
        description="True = propagated to all charts; False = chart-specific"
    )
    reasoning: str = Field(default="", description="Why this dimension was recommended")


class GlobalFilterConfig(BaseModel):
    """Complete filter configuration for a dashboard."""
    filters: List[FilterDimension] = Field(default_factory=list)
    primary_date_field: Optional[str] = None
    primary_date_table: Optional[str] = None
    reasoning: str = ""
    refinement_suggestions: List[str] = Field(
        default_factory=list,
        description="Natural-language hints the user can act on to refine further"
    )
    source: str = "global_filter_recommender"


# ===========================================================================
# Example + instruction catalog  (hardcoded; swap for vector store later)
# ===========================================================================

class FilterExample(BaseModel):
    """A reference GlobalFilterConfig paired with a domain tag and description."""
    domain: str
    description: str
    # Serialised GlobalFilterConfig — kept as dict so it renders cleanly in prompts
    config: Dict[str, Any]


class FilterInstruction(BaseModel):
    """Domain-specific rules and anti-patterns for filter design."""
    domain: str
    rules: List[str]
    anti_patterns: List[str]


# ---------------------------------------------------------------------------
# Hardcoded example catalog
# ---------------------------------------------------------------------------

_EXAMPLE_CATALOG: List[FilterExample] = [
    FilterExample(
        domain="training_compliance",
        description=(
            "LMS / CSOD training completion dashboards — metrics include completion "
            "rate, overdue training, certification status, course enrollments."
        ),
        config={
            "filters": [
                {
                    "id": "completion_date_range",
                    "label": "Completion Date Range",
                    "filter_type": "date_range",
                    "column": "completion_date",
                    "table": "lms_completions",
                    "sql_fragment": "completion_date BETWEEN :start_date AND :end_date",
                    "operator": "BETWEEN",
                    "default_value": {"start": "2024-01-01", "end": "2024-12-31"},
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": (
                        "completion_date is the primary temporal axis across all "
                        "training metrics; required for trend analysis."
                    ),
                },
                {
                    "id": "department_filter",
                    "label": "Department",
                    "filter_type": "multi_select",
                    "column": "department_name",
                    "table": "hr_employees",
                    "sql_fragment": "department_name IN (:departments)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": (
                        "Department is the most common organisational slice; "
                        "appears as a dimension in every training metric."
                    ),
                },
                {
                    "id": "course_type_filter",
                    "label": "Course Type",
                    "filter_type": "multi_select",
                    "column": "course_type",
                    "table": "lms_courses",
                    "sql_fragment": "course_type IN (:course_types)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["Training Completion Rate", "Overdue Training Count"],
                    "is_global": False,
                    "reasoning": (
                        "Course type (mandatory vs. elective) changes compliance "
                        "thresholds and should be filterable independently."
                    ),
                },
                {
                    "id": "compliance_status_filter",
                    "label": "Compliance Status",
                    "filter_type": "single_select",
                    "column": "compliance_status",
                    "table": "lms_completions",
                    "sql_fragment": "compliance_status = :status",
                    "operator": "=",
                    "default_value": None,
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": (
                        "Allows instant focus on compliant vs. non-compliant employees "
                        "across the entire dashboard."
                    ),
                },
                {
                    "id": "location_filter",
                    "label": "Location / Site",
                    "filter_type": "multi_select",
                    "column": "location_name",
                    "table": "hr_employees",
                    "sql_fragment": "location_name IN (:locations)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": (
                        "Regulatory requirements often differ by site; location "
                        "filtering is critical for multi-site compliance reporting."
                    ),
                },
            ],
            "primary_date_field": "completion_date",
            "primary_date_table": "lms_completions",
            "reasoning": (
                "These five filters cover the key compliance dimensions: time window, "
                "organisational unit, course category, compliance state, and geography."
            ),
            "refinement_suggestions": [
                "Add a 'Job Role' filter if regulations differ by role (e.g. OSHA job classifications).",
                "Add a 'Manager' filter to enable team-level drill-down reporting.",
                "Consider a 'Due Date' range filter to surface upcoming deadlines.",
            ],
        },
    ),

    FilterExample(
        domain="workforce_analytics",
        description=(
            "HR workforce dashboards — headcount, attrition, tenure, hiring pipeline, "
            "diversity metrics."
        ),
        config={
            "filters": [
                {
                    "id": "hire_date_range",
                    "label": "Hire Date Range",
                    "filter_type": "date_range",
                    "column": "hire_date",
                    "table": "hr_employees",
                    "sql_fragment": "hire_date BETWEEN :start_date AND :end_date",
                    "operator": "BETWEEN",
                    "default_value": {"start": "2020-01-01", "end": "2024-12-31"},
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Hire date is the primary temporal dimension for workforce cohort analysis.",
                },
                {
                    "id": "department_filter",
                    "label": "Department",
                    "filter_type": "multi_select",
                    "column": "department_name",
                    "table": "hr_employees",
                    "sql_fragment": "department_name IN (:departments)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Core segmentation dimension for all HR KPIs.",
                },
                {
                    "id": "employment_type_filter",
                    "label": "Employment Type",
                    "filter_type": "single_select",
                    "column": "employment_type",
                    "table": "hr_employees",
                    "sql_fragment": "employment_type = :type",
                    "operator": "=",
                    "default_value": None,
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Full-time vs. part-time vs. contractor distinctions affect most workforce KPIs.",
                },
                {
                    "id": "tenure_range_filter",
                    "label": "Tenure (years)",
                    "filter_type": "numeric_range",
                    "column": "tenure_years",
                    "table": "hr_employees",
                    "sql_fragment": "tenure_years BETWEEN :min_tenure AND :max_tenure",
                    "operator": "BETWEEN",
                    "default_value": None,
                    "applies_to": ["Attrition Rate", "Retention Score"],
                    "is_global": False,
                    "reasoning": "Tenure bands are key for attrition risk segmentation.",
                },
            ],
            "primary_date_field": "hire_date",
            "primary_date_table": "hr_employees",
            "reasoning": (
                "Workforce dashboards require time cohort analysis, organisational "
                "segmentation, and contract-type breakdowns."
            ),
            "refinement_suggestions": [
                "Add a 'Cost Centre' filter for financial HR reporting.",
                "Add a 'Manager Level' filter for leadership span-of-control analysis.",
            ],
        },
    ),

    FilterExample(
        domain="safety_compliance",
        description=(
            "EHS / safety dashboards — incident rates, near-miss reports, "
            "safety training, OSHA recordables."
        ),
        config={
            "filters": [
                {
                    "id": "incident_date_range",
                    "label": "Incident Date Range",
                    "filter_type": "date_range",
                    "column": "incident_date",
                    "table": "safety_incidents",
                    "sql_fragment": "incident_date BETWEEN :start_date AND :end_date",
                    "operator": "BETWEEN",
                    "default_value": {"start": "2024-01-01", "end": "2024-12-31"},
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "All EHS metrics are anchored to incident or inspection date.",
                },
                {
                    "id": "site_filter",
                    "label": "Site / Facility",
                    "filter_type": "multi_select",
                    "column": "site_name",
                    "table": "safety_incidents",
                    "sql_fragment": "site_name IN (:sites)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "OSHA reporting is site-specific; site is the primary segmentation dimension.",
                },
                {
                    "id": "incident_type_filter",
                    "label": "Incident Type",
                    "filter_type": "multi_select",
                    "column": "incident_type",
                    "table": "safety_incidents",
                    "sql_fragment": "incident_type IN (:types)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["Incident Rate", "Near Miss Rate"],
                    "is_global": False,
                    "reasoning": "Recordable vs. near-miss vs. first-aid incidents require separate analysis tracks.",
                },
                {
                    "id": "severity_filter",
                    "label": "Severity Level",
                    "filter_type": "single_select",
                    "column": "severity",
                    "table": "safety_incidents",
                    "sql_fragment": "severity = :severity",
                    "operator": "=",
                    "default_value": None,
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Severity filtering isolates critical incidents for executive reporting.",
                },
            ],
            "primary_date_field": "incident_date",
            "primary_date_table": "safety_incidents",
            "reasoning": "EHS dashboards need time, site, type, and severity filters to satisfy OSHA and internal SLA reporting.",
            "refinement_suggestions": [
                "Add a 'Shift' filter if incident patterns differ by shift rotation.",
                "Add a 'Root Cause Category' filter to support corrective action tracking.",
            ],
        },
    ),

    FilterExample(
        domain="certification_compliance",
        description=(
            "License, certification, and credentialing dashboards — expiry tracking, "
            "renewal rates, regulatory body reporting."
        ),
        config={
            "filters": [
                {
                    "id": "expiry_date_range",
                    "label": "Certification Expiry Window",
                    "filter_type": "date_range",
                    "column": "expiry_date",
                    "table": "employee_certifications",
                    "sql_fragment": "expiry_date BETWEEN :start_date AND :end_date",
                    "operator": "BETWEEN",
                    "default_value": {"start": "2024-01-01", "end": "2024-12-31"},
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Expiry date drives all certification compliance KPIs.",
                },
                {
                    "id": "certification_type_filter",
                    "label": "Certification Type",
                    "filter_type": "multi_select",
                    "column": "certification_type",
                    "table": "employee_certifications",
                    "sql_fragment": "certification_type IN (:cert_types)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Different certification types have different regulatory deadlines and renewal windows.",
                },
                {
                    "id": "cert_status_filter",
                    "label": "Certification Status",
                    "filter_type": "single_select",
                    "column": "cert_status",
                    "table": "employee_certifications",
                    "sql_fragment": "cert_status = :status",
                    "operator": "=",
                    "default_value": "expiring_soon",
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Defaulting to 'expiring_soon' surfaces the highest-risk employees immediately.",
                },
                {
                    "id": "job_role_filter",
                    "label": "Job Role",
                    "filter_type": "multi_select",
                    "column": "job_role",
                    "table": "hr_employees",
                    "sql_fragment": "job_role IN (:roles)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Mandatory certifications are role-specific; role filtering isolates applicable requirements.",
                },
            ],
            "primary_date_field": "expiry_date",
            "primary_date_table": "employee_certifications",
            "reasoning": "Certification dashboards are expiry-driven and must support filtering by cert type, status, and role.",
            "refinement_suggestions": [
                "Add a 'Regulatory Body' filter if you need to separate OSHA from state-level requirements.",
                "Add a 'Days Until Expiry' numeric filter to highlight the most urgent cases.",
            ],
        },
    ),

    FilterExample(
        domain="performance_management",
        description=(
            "Performance review dashboards — review cycle completion, rating distributions, "
            "goal achievement, calibration metrics."
        ),
        config={
            "filters": [
                {
                    "id": "review_period_filter",
                    "label": "Review Period",
                    "filter_type": "single_select",
                    "column": "review_period",
                    "table": "performance_reviews",
                    "sql_fragment": "review_period = :period",
                    "operator": "=",
                    "default_value": "2024-H1",
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Performance reviews are cycle-based; period is the primary segmentation axis.",
                },
                {
                    "id": "department_filter",
                    "label": "Department",
                    "filter_type": "multi_select",
                    "column": "department_name",
                    "table": "hr_employees",
                    "sql_fragment": "department_name IN (:departments)",
                    "operator": "IN",
                    "default_value": [],
                    "applies_to": ["all"],
                    "is_global": True,
                    "reasoning": "Departmental benchmarking is the primary use case for performance dashboards.",
                },
                {
                    "id": "rating_range_filter",
                    "label": "Performance Rating",
                    "filter_type": "numeric_range",
                    "column": "overall_rating",
                    "table": "performance_reviews",
                    "sql_fragment": "overall_rating BETWEEN :min_rating AND :max_rating",
                    "operator": "BETWEEN",
                    "default_value": None,
                    "applies_to": ["Rating Distribution", "High Performer Rate"],
                    "is_global": False,
                    "reasoning": "Isolating rating bands (e.g. top 10%) is essential for talent planning.",
                },
                {
                    "id": "review_status_filter",
                    "label": "Review Status",
                    "filter_type": "single_select",
                    "column": "review_status",
                    "table": "performance_reviews",
                    "sql_fragment": "review_status = :status",
                    "operator": "=",
                    "default_value": "completed",
                    "applies_to": ["Completion Rate"],
                    "is_global": False,
                    "reasoning": "Separating completed from in-progress reviews prevents partial-cycle distortions.",
                },
            ],
            "primary_date_field": "review_period",
            "primary_date_table": "performance_reviews",
            "reasoning": "Performance dashboards need cycle, department, and rating-band filtering to support calibration workflows.",
            "refinement_suggestions": [
                "Add a 'Manager' filter to enable manager-level calibration views.",
                "Add a 'Goal Category' filter to separate individual vs. team goals.",
            ],
        },
    ),
]


# ---------------------------------------------------------------------------
# Hardcoded instruction catalog
# ---------------------------------------------------------------------------

_INSTRUCTION_CATALOG: List[FilterInstruction] = [
    FilterInstruction(
        domain="general",
        rules=[
            "Always include exactly ONE primary date-range filter as the temporal anchor for all charts.",
            "Prefer columns that appear in ≥2 metric source tables — these make the best global filters.",
            "Label filters in business language, never in technical column names (use 'Department' not 'dept_id').",
            "Set 'applies_to': ['all'] for truly global filters; list specific metric names for chart-scoped filters.",
            "Provide a default_value when it significantly improves the out-of-the-box dashboard experience.",
            "Limit to 3-7 filters — more than 7 overwhelms users; fewer than 3 feels underutilised.",
            "For multi_select filters, always use the IN operator with a list parameter.",
            "For date_range filters, always use BETWEEN with :start_date and :end_date parameters.",
            "Numeric range filters (e.g. score, tenure) should only appear when the KPI has a clear threshold.",
            "sql_fragment must be a standalone WHERE clause condition, not a full SELECT or WHERE keyword.",
        ],
        anti_patterns=[
            "Do NOT create a filter that only applies to a single chart — that belongs in chart config, not global filters.",
            "Do NOT include primary-key columns (id, uuid) as filter dimensions.",
            "Do NOT create duplicate filters for the same column even if it appears in multiple tables.",
            "Do NOT use SELECT or WHERE keywords inside sql_fragment — it is a condition only.",
            "Do NOT recommend more than one date-range filter unless the domain genuinely requires it (e.g. hire_date vs. termination_date for attrition).",
            "Do NOT suggest free-text search filters — they are chart-specific UI concerns.",
            "Do NOT set is_global=False unless the filter truly cannot logically apply across all charts.",
        ],
    ),
    FilterInstruction(
        domain="training_compliance",
        rules=[
            "completion_date or training_date must be the primary date-range filter.",
            "compliance_status (compliant / non-compliant / overdue) is almost always a useful global filter.",
            "department_name or org_unit is the standard organisational segmentation dimension for LMS data.",
            "course_type (mandatory vs. elective) should be chart-scoped, not global, because compliance thresholds differ.",
            "Include a location/site filter if the dataset contains multiple operating locations.",
        ],
        anti_patterns=[
            "Do NOT make course_id a global filter — use course_type or course_category instead.",
            "Do NOT make employee_id or user_id filterable — those are row-level, not dimension-level.",
        ],
    ),
    FilterInstruction(
        domain="safety_compliance",
        rules=[
            "incident_date must be the primary date-range filter.",
            "site_name or facility is the primary safety segmentation dimension (OSHA is site-reported).",
            "severity level should always be a global filter for executive safety dashboards.",
            "incident_type (recordable / near-miss / first-aid) should be chart-scoped because aggregation rules differ.",
        ],
        anti_patterns=[
            "Do NOT use employee_id or incident_id as a filter dimension.",
            "Do NOT include free-text root_cause as a filter — use root_cause_category instead.",
        ],
    ),
    FilterInstruction(
        domain="certification_compliance",
        rules=[
            "expiry_date must be the primary date filter — not issue_date.",
            "Default cert_status to 'expiring_soon' to surface risk immediately.",
            "certification_type should be global because different cert types have different regulatory deadlines.",
            "job_role is required whenever certifications are role-specific (most healthcare/safety domains).",
        ],
        anti_patterns=[
            "Do NOT use issue_date as the primary date filter — expiry is the compliance-relevant anchor.",
            "Do NOT make license_number or cert_id a filterable dimension.",
        ],
    ),
]


# ---------------------------------------------------------------------------
# FilterExampleProvider  — interface ready for vector-store swap
# ---------------------------------------------------------------------------

class FilterExampleProvider:
    """
    Returns domain-matched examples and instructions for prompt injection.

    Currently backed by hardcoded catalogs.  To switch to a vector store:
      1. Override ``_load_examples`` to call your retrieval client.
      2. Override ``_load_instructions`` similarly.
      The public interface (``get_examples``, ``get_instructions``) is unchanged.
    """

    # -- Public API ----------------------------------------------------------

    def get_examples(
        self,
        intent: str,
        schemas: Optional[List[Dict[str, Any]]] = None,
        max_examples: int = 2,
    ) -> List[FilterExample]:
        """
        Return the most relevant example configs for the given intent.
        Matched by domain keywords in intent string and table names from schemas.
        """
        domain = self._detect_domain(intent, schemas or [])
        examples = self._load_examples()

        # Primary: exact domain match
        matched = [e for e in examples if e.domain == domain]

        # Fallback: always include the training_compliance example (most common)
        if not matched:
            matched = [e for e in examples if e.domain == "training_compliance"]

        # Secondary: fill remaining slots with general examples from other domains
        remaining = [e for e in examples if e not in matched]
        matched = (matched + remaining)[:max_examples]
        return matched

    def get_instructions(self, intent: str, schemas: Optional[List[Dict[str, Any]]] = None) -> FilterInstruction:
        """Return domain-specific + general instructions merged into one object."""
        domain = self._detect_domain(intent, schemas or [])
        all_instructions = self._load_instructions()

        general = next((i for i in all_instructions if i.domain == "general"), None)
        domain_specific = next((i for i in all_instructions if i.domain == domain), None)

        # Merge: domain rules first, then general rules not already covered
        rules = list(domain_specific.rules if domain_specific else [])
        anti = list(domain_specific.anti_patterns if domain_specific else [])
        if general:
            rules += [r for r in general.rules if r not in rules]
            anti += [r for r in general.anti_patterns if r not in anti]

        return FilterInstruction(
            domain=domain,
            rules=rules,
            anti_patterns=anti,
        )

    # -- Subclass hooks (swap for vector store here) -------------------------

    def _load_examples(self) -> List[FilterExample]:
        """Return the full example catalog. Replace with vector store retrieval."""
        return _EXAMPLE_CATALOG

    def _load_instructions(self) -> List[FilterInstruction]:
        """Return the full instruction catalog. Replace with vector store retrieval."""
        return _INSTRUCTION_CATALOG

    # -- Domain detection ----------------------------------------------------

    def _detect_domain(
        self,
        intent: str,
        schemas: List[Dict[str, Any]],
    ) -> str:
        """
        Infer domain from the intent string and schema table names.
        Returns a domain key matching the catalogs above.
        """
        text = intent.lower()
        # Collect table name tokens for additional signal
        for s in schemas[:8]:
            tname = (s.get("table_name") or s.get("name") or "").lower()
            text += " " + tname

        if any(k in text for k in ("safety", "incident", "ehs", "osha", "near_miss", "hazard")):
            return "safety_compliance"
        if any(k in text for k in ("certif", "license", "credential", "expir", "renewal")):
            return "certification_compliance"
        if any(k in text for k in ("performance", "review", "rating", "calibration", "goal")):
            return "performance_management"
        if any(k in text for k in ("workforce", "headcount", "attrition", "hiring", "tenure", "diversity")):
            return "workforce_analytics"
        # Default — LMS / training compliance is the most common CSOD use case
        return "training_compliance"


# Singleton — one instance shared across calls (no state)
_example_provider = FilterExampleProvider()


def get_example_provider() -> FilterExampleProvider:
    """Return the shared FilterExampleProvider instance."""
    return _example_provider


# ===========================================================================
# Prompt templates
# ===========================================================================

_RECOMMEND_PROMPT = """\
You are a data modelling expert helping configure an interactive compliance dashboard.

## Filter design instructions
{instructions_text}

## Anti-patterns to avoid
{anti_patterns_text}

## Reference examples
{examples_text}

---

## Current request context
User intent: {intent}
User query: {user_query}

## Available MDL schemas (silver/gold tables)
{schemas_summary}

## Selected metrics and KPIs
{metrics_summary}

## Generated gold model SQL (columns already computed)
{gold_sql_summary}

---

## Task
Using the instructions and examples above as guidance, recommend 3-7 filter dimensions
for this specific dashboard.  Ground every filter in an actual column from the schemas
or gold model above — do not invent columns.

Return ONLY valid JSON (no markdown, no commentary):
{{
  "filters": [
    {{
      "id": "<snake_case_id>",
      "label": "<Human Label>",
      "filter_type": "date_range|single_select|multi_select|numeric_range|boolean",
      "column": "<column_name>",
      "table": "<table_name>",
      "sql_fragment": "<parameterised WHERE clause condition only>",
      "operator": "BETWEEN|IN|=|>=|<=",
      "default_value": null,
      "applies_to": ["all"],
      "is_global": true,
      "reasoning": "<1-sentence rationale>"
    }}
  ],
  "primary_date_field": "<date column>",
  "primary_date_table": "<table>",
  "reasoning": "<2-3 sentence overall rationale>",
  "refinement_suggestions": [
    "<what the user could ask next to improve these filters>"
  ]
}}
"""

_REFINE_PROMPT = """\
You are refining the global filter configuration for a compliance dashboard
based on a follow-up question from the user.

## Filter design instructions
{instructions_text}

## Anti-patterns to avoid
{anti_patterns_text}

## Current filter configuration
{current_config}

## Conversation history
{history}

## User's latest message
{user_message}

---

## Task
Update the filter configuration to address the user's feedback while
keeping all existing filter rules and anti-patterns in mind.
You may add, remove, or modify filters and refinement_suggestions.

Return ONLY valid JSON in the same GlobalFilterConfig shape.
"""


def _render_instructions(instruction: FilterInstruction) -> tuple[str, str]:
    """Return (rules_text, anti_patterns_text) formatted for prompts."""
    rules = "\n".join(f"  • {r}" for r in instruction.rules)
    antis = "\n".join(f"  • {a}" for a in instruction.anti_patterns)
    return rules, antis


def _render_examples(examples: List[FilterExample]) -> str:
    """Render examples as labelled JSON blocks for the prompt."""
    parts: List[str] = []
    for ex in examples:
        parts.append(
            f"### Example — {ex.domain}\n"
            f"When to use: {ex.description}\n"
            f"```json\n{json.dumps(ex.config, indent=2)}\n```"
        )
    return "\n\n".join(parts) if parts else "(no examples available)"


# ===========================================================================
# Core recommender class
# ===========================================================================

class GlobalFilterRecommender:
    """LLM-backed recommender that produces and refines GlobalFilterConfig."""

    def __init__(
        self,
        timeout: float = 30.0,
        example_provider: Optional[FilterExampleProvider] = None,
    ) -> None:
        self._timeout = timeout
        self._examples = example_provider or get_example_provider()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def recommend(
        self,
        resolved_schemas: List[Dict[str, Any]],
        metric_recommendations: List[Dict[str, Any]],
        kpi_recommendations: List[Dict[str, Any]],
        gold_model_sql: List[Dict[str, Any]],
        intent: str = "",
        user_query: str = "",
    ) -> GlobalFilterConfig:
        """Generate initial GlobalFilterConfig from workflow state."""
        instruction = self._examples.get_instructions(intent, resolved_schemas)
        examples = self._examples.get_examples(intent, resolved_schemas, max_examples=2)
        rules_text, anti_text = _render_instructions(instruction)
        examples_text = _render_examples(examples)

        prompt = _RECOMMEND_PROMPT.format(
            instructions_text=rules_text,
            anti_patterns_text=anti_text,
            examples_text=examples_text,
            intent=intent or "metrics_dashboard",
            user_query=user_query[:400] if user_query else "Build a compliance dashboard",
            schemas_summary=_summarise_schemas(resolved_schemas),
            metrics_summary=_summarise_metrics(metric_recommendations, kpi_recommendations),
            gold_sql_summary=_summarise_gold_sql(gold_model_sql),
        )

        raw = await self._invoke_llm(prompt)
        return _parse_filter_config(raw)

    async def refine(
        self,
        current_config: GlobalFilterConfig,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        intent: str = "",
    ) -> GlobalFilterConfig:
        """Refine an existing GlobalFilterConfig based on user follow-up."""
        instruction = self._examples.get_instructions(intent)
        rules_text, anti_text = _render_instructions(instruction)

        prompt = _REFINE_PROMPT.format(
            instructions_text=rules_text,
            anti_patterns_text=anti_text,
            current_config=current_config.model_dump_json(indent=2),
            history=_format_history(history or []),
            user_message=user_message[:600],
        )
        raw = await self._invoke_llm(prompt)
        return _parse_filter_config(raw, fallback=current_config)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _invoke_llm(self, prompt: str) -> str:
        from app.core.dependencies import get_llm
        llm = get_llm()
        try:
            resp = await asyncio.wait_for(llm.ainvoke(prompt), timeout=self._timeout)
            return resp.content if hasattr(resp, "content") else str(resp)
        except asyncio.TimeoutError:
            logger.warning("GlobalFilterRecommender LLM timed out")
            return "{}"
        except Exception as exc:
            logger.warning("GlobalFilterRecommender LLM error: %s", exc)
            return "{}"


# ===========================================================================
# Context summarisers
# ===========================================================================

def _summarise_schemas(schemas: List[Dict[str, Any]]) -> str:
    if not schemas:
        return "No schema information available."
    lines: List[str] = []
    for s in schemas[:12]:
        table = s.get("table_name") or s.get("name", "unknown")
        cols = s.get("columns") or s.get("column_metadata", [])
        col_strs: List[str] = []
        for c in (cols or [])[:15]:
            if isinstance(c, dict):
                cname = c.get("column_name") or c.get("name", "")
                dtype = c.get("data_type") or c.get("type", "")
                if cname:
                    col_strs.append(f"{cname}({dtype})" if dtype else cname)
            elif isinstance(c, str):
                col_strs.append(c)
        lines.append(f"  {table}: {', '.join(col_strs) or 'no columns listed'}")
    return "\n".join(lines)


def _summarise_metrics(
    metrics: List[Dict[str, Any]],
    kpis: List[Dict[str, Any]],
) -> str:
    items: List[str] = []
    for m in (metrics or [])[:8]:
        name = m.get("name") or m.get("metric_name", "")
        src = ", ".join((m.get("source_tables") or m.get("source_schemas", [])) or [])
        if name:
            items.append(f"  [metric] {name}" + (f" (tables: {src})" if src else ""))
    for k in (kpis or [])[:8]:
        name = k.get("name") or k.get("kpi_name", "")
        src = ", ".join((k.get("source_tables") or k.get("source_schemas", [])) or [])
        if name:
            items.append(f"  [kpi]    {name}" + (f" (tables: {src})" if src else ""))
    return "\n".join(items) if items else "No metrics selected yet."


def _summarise_gold_sql(gold_models: List[Dict[str, Any]]) -> str:
    if not gold_models:
        return "No gold models generated."
    lines: List[str] = []
    for m in gold_models[:5]:
        name = m.get("name", "unnamed")
        cols = m.get("expected_columns") or []
        col_names = [
            (c.get("name") or c.get("column_name") or str(c)) if isinstance(c, dict) else str(c)
            for c in cols[:10]
        ]
        sql_snippet = (m.get("sql_query") or "")[:200].replace("\n", " ")
        lines.append(
            f"  {name}: columns=[{', '.join(col_names)}]\n"
            f"    SQL: {sql_snippet}..."
        )
    return "\n".join(lines)


def _format_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return "(no prior conversation)"
    lines = []
    for turn in history[-6:]:
        role = turn.get("role", "user")
        msg = turn.get("content", "")[:300]
        lines.append(f"{role.upper()}: {msg}")
    return "\n".join(lines)


# ===========================================================================
# JSON parsing
# ===========================================================================

def _parse_filter_config(
    raw: str,
    fallback: Optional[GlobalFilterConfig] = None,
) -> GlobalFilterConfig:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        data = json.loads(cleaned)
        filters = []
        for f in data.get("filters", []):
            try:
                filters.append(FilterDimension(**f))
            except Exception as exc:
                logger.debug("Skipping malformed filter entry: %s — %s", f, exc)
        return GlobalFilterConfig(
            filters=filters,
            primary_date_field=data.get("primary_date_field"),
            primary_date_table=data.get("primary_date_table"),
            reasoning=data.get("reasoning", ""),
            refinement_suggestions=data.get("refinement_suggestions", []),
        )
    except Exception as exc:
        logger.warning("GlobalFilterRecommender could not parse LLM response: %s", exc)
        return fallback or GlobalFilterConfig(
            reasoning="Filter configuration could not be generated; please retry.",
            refinement_suggestions=["Try rephrasing your dashboard goals."],
        )
