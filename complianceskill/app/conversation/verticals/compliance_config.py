"""
Compliance Agent Conversation Configuration

Defines scoping question templates and conversation config for the Compliance workflow.
"""
from app.conversation.config import ScopingQuestionTemplate
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.verticals.security_shared import SECURITY_SHARED_TEMPLATES

# Shared framework options for all security agents
FRAMEWORK_OPTIONS = [
    {"id": "nist_csf", "label": "NIST CSF", "description": "NIST Cybersecurity Framework"},
    {"id": "soc2", "label": "SOC 2", "description": "SOC 2 Trust Services Criteria"},
    {"id": "hipaa", "label": "HIPAA", "description": "Health Insurance Portability and Accountability Act"},
    {"id": "iso27001", "label": "ISO 27001", "description": "ISO/IEC 27001 Information Security Management"},
    {"id": "pci_dss", "label": "PCI DSS", "description": "Payment Card Industry Data Security Standard"},
    {"id": "cis_controls", "label": "CIS Controls", "description": "Center for Internet Security Controls"},
]

# Shared datasource options for all security agents
DATASOURCE_OPTIONS = [
    {"id": "qualys", "label": "Qualys"},
    {"id": "crowdstrike", "label": "CrowdStrike"},
    {"id": "okta", "label": "Okta"},
    {"id": "splunk", "label": "Splunk"},
    {"id": "sentinel", "label": "Azure Sentinel"},
    {"id": "wiz", "label": "Wiz"},
    {"id": "snyk", "label": "Snyk"},
    {"id": "elastic", "label": "Elastic"},
]

# Compliance-specific scoping question templates
# Start with shared templates, then add compliance-specific ones
COMPLIANCE_SCOPING_TEMPLATES = {
    **SECURITY_SHARED_TEMPLATES,  # severity, time_period, environment, threat_scenario, persona
    "asset_type": ScopingQuestionTemplate(
        filter_name="asset_type",
        question_id="asset_type",
        label="What type of assets are in scope?",
        interaction_mode="multi",
        options=[
            {"id": "servers", "label": "Servers"},
            {"id": "containers", "label": "Containers"},
            {"id": "cloud_resources", "label": "Cloud Resources"},
            {"id": "applications", "label": "Applications"},
            {"id": "databases", "label": "Databases"},
        ],
        state_key="asset_type",
        required=False,
    ),
    "assessment_scope": ScopingQuestionTemplate(
        filter_name="assessment_scope",
        question_id="assessment_scope",
        label="What should the analysis cover?",
        interaction_mode="single",
        options=[
            {"id": "controls_only", "label": "Controls Only"},
            {"id": "controls_and_evidence", "label": "Controls and Evidence"},
            {"id": "full_assessment", "label": "Full Assessment"},
        ],
        state_key="assessment_scope",
        required=False,
    ),
    "secondary_frameworks": ScopingQuestionTemplate(
        filter_name="secondary_frameworks",
        question_id="secondary_framework_ids",
        label="Which other frameworks should I map to?",
        interaction_mode="multi",
        options=[],  # Populated dynamically, excluding primary framework
        state_key="secondary_framework_ids",
        required=False,
    ),
}

# Compliance intent options
COMPLIANCE_INTENT_OPTIONS = [
    {
        "id": "detection_engineering",
        "label": "Write detection rules and SIEM queries",
        "description": "Generate SIEM rules, sigma rules, and detection logic for a specific framework and threat",
    },
    {
        "id": "risk_control_mapping",
        "label": "Map risks to controls",
        "description": "Identify which controls apply to your risks across your security stack",
    },
    {
        "id": "gap_analysis",
        "label": "Find compliance gaps",
        "description": "Identify what is missing against a framework — controls not implemented, evidence not collected",
    },
    {
        "id": "cross_framework_mapping",
        "label": "Map across multiple frameworks",
        "description": "See how your controls satisfy NIST, ISO 27001, SOC 2, and HIPAA simultaneously",
    },
    {
        "id": "dashboard_generation",
        "label": "Build a compliance dashboard",
        "description": "Generate a dashboard showing compliance posture, control coverage, and risk metrics",
    },
]

# Compliance conversation config
COMPLIANCE_CONVERSATION_CONFIG = SecurityConversationConfig(
    agent_id="compliance",
    display_name="Compliance Agent",
    framework_options=FRAMEWORK_OPTIONS,
    datasource_options=DATASOURCE_OPTIONS,
    template_options=None,  # Compliance has no template concept
    scoping_question_templates=COMPLIANCE_SCOPING_TEMPLATES,
    always_include_filters=["severity", "time_period"],
    intent_options=COMPLIANCE_INTENT_OPTIONS,
    requires_execution_preview=True,  # Compliance has multi-step planner
    intent_to_workflow={
        "detection_engineering": "compliance_workflow",
        "risk_control_mapping": "compliance_workflow",
        "gap_analysis": "compliance_workflow",
        "cross_framework_mapping": "compliance_workflow",
        "dashboard_generation": "compliance_workflow",
    },
    state_key_prefix="compliance",
    max_scoping_questions_per_turn=3,
)
