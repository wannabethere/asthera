"""
Detection & Triage Agent Conversation Configuration

Defines scoping question templates and conversation config for the DT workflow.
"""
from app.conversation.config import ScopingQuestionTemplate
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.verticals.compliance_config import FRAMEWORK_OPTIONS, DATASOURCE_OPTIONS
from app.conversation.verticals.security_shared import SECURITY_SHARED_TEMPLATES

# DT-specific scoping question templates
# Start with shared templates, then add DT-specific ones
DT_SCOPING_TEMPLATES = {
    **{k: v for k, v in SECURITY_SHARED_TEMPLATES.items() if k != "persona"},  # severity, time_period, environment, threat_scenario
    "is_leen_request": ScopingQuestionTemplate(
        filter_name="is_leen_request",
        question_id="is_leen_request",
        label="Are you requesting Cube.js schema output?",
        interaction_mode="single",
        options=[
            {"id": "yes", "label": "Yes"},
            {"id": "no", "label": "No"},
        ],
        state_key="is_leen_request",
        required=False,
    ),
    "generate_sql": ScopingQuestionTemplate(
        filter_name="generate_sql",
        question_id="generate_sql",
        label="Should I generate dbt-compatible gold model SQL?",
        interaction_mode="single",
        options=[
            {"id": "yes", "label": "Yes"},
            {"id": "no", "label": "No"},
        ],
        state_key="generate_sql",
        required=False,
    ),
    "persona": ScopingQuestionTemplate(
        filter_name="persona",
        question_id="dt_dashboard_persona",
        label="Who is the dashboard for?",
        interaction_mode="single",
        options=SECURITY_SHARED_TEMPLATES["persona"].options,  # Reuse shared options
        state_key="dt_dashboard_persona",  # Different state key for DT
        required=False,
    ),
}

# DT template options (first question)
DT_TEMPLATE_OPTIONS = [
    {
        "id": "A",
        "label": "Detection rules only",
        "description": "SIEM rules, sigma rules, detection queries — no triage recommendations. Runs: detection_engineer → siem_rule_validator → metric_calculation_validator → playbook_assembler.",
    },
    {
        "id": "B",
        "label": "Triage recommendations only",
        "description": "Metric recommendations and triage guidance — no SIEM rules generated. Runs: metric_feasibility_filter → triage_engineer → metric_calculation_validator → playbook_assembler.",
    },
    {
        "id": "C",
        "label": "Full pipeline — detection + triage",
        "description": "SIEM rules first, then triage recommendations that reference detection output. Runs both engineer paths in sequence.",
    },
    {
        "id": "dashboard",
        "label": "Dashboard for detection metrics",
        "description": "Generate a dashboard showing detection coverage, alert volume, and triage KPIs. Bypasses detection and triage engineers entirely.",
    },
]

# DT intent options (for reference, though DT uses template instead)
DT_INTENT_OPTIONS = [
    {
        "id": "detection_engineering",
        "label": "Write detection rules and SIEM queries",
        "description": "Generate SIEM rules, sigma rules, and detection logic",
    },
    {
        "id": "triage_engineering",
        "label": "Generate triage recommendations",
        "description": "Metric recommendations and triage guidance",
    },
    {
        "id": "full_pipeline",
        "label": "Full detection and triage pipeline",
        "description": "Both detection rules and triage recommendations",
    },
    {
        "id": "dashboard_generation",
        "label": "Build a detection dashboard",
        "description": "Generate a dashboard showing detection coverage and KPIs",
    },
]

# DT conversation config
DT_CONVERSATION_CONFIG = SecurityConversationConfig(
    agent_id="detection_triage",
    display_name="Detection & Triage Agent",
    framework_options=FRAMEWORK_OPTIONS,
    datasource_options=DATASOURCE_OPTIONS,
    template_options=DT_TEMPLATE_OPTIONS,
    scoping_question_templates=DT_SCOPING_TEMPLATES,
    always_include_filters=["time_period"],  # severity and threat_scenario are conditional
    intent_options=DT_INTENT_OPTIONS,
    requires_execution_preview=False,  # DT has single-path pipeline
    intent_to_workflow={
        "detection_engineering": "dt_workflow",
        "triage_engineering": "dt_workflow",
        "full_pipeline": "dt_workflow",
        "dashboard_generation": "dt_workflow",
    },
    state_key_prefix="dt",
    max_scoping_questions_per_turn=3,
)
