"""
Shared Security Agent Templates

Common scoping question templates used by both Compliance and DT agents.
"""
from app.conversation.config import ScopingQuestionTemplate

# Shared scoping question templates for security agents
SECURITY_SHARED_TEMPLATES = {
    "severity": ScopingQuestionTemplate(
        filter_name="severity",
        question_id="severity_filter",
        label="Which severity levels should I focus on?",
        interaction_mode="multi",
        options=[
            {"id": "critical", "label": "Critical"},
            {"id": "high", "label": "High"},
            {"id": "medium", "label": "Medium"},
            {"id": "low", "label": "Low"},
        ],
        state_key="severity_filter",
        required=True,
    ),
    "time_period": ScopingQuestionTemplate(
        filter_name="time_period",
        question_id="time_window",
        label="What time window matters most?",
        interaction_mode="single",
        options=[
            {"id": "last_7_days", "label": "Last 7 days"},
            {"id": "last_30_days", "label": "Last 30 days"},
            {"id": "last_90_days", "label": "Last 90 days"},
            {"id": "last_quarter", "label": "Last quarter"},
            {"id": "last_year", "label": "Last year"},
        ],
        state_key="time_window",
        required=True,
    ),
    "environment": ScopingQuestionTemplate(
        filter_name="environment",
        question_id="environment",
        label="Which environment should I analyse?",
        interaction_mode="single",
        options=[
            {"id": "production", "label": "Production"},
            {"id": "staging", "label": "Staging"},
            {"id": "development", "label": "Development"},
            {"id": "all", "label": "All environments"},
        ],
        state_key="environment",
        required=False,
    ),
    "threat_scenario": ScopingQuestionTemplate(
        filter_name="threat_scenario",
        question_id="threat_scenario",
        label="What threat scenario are you focused on?",
        interaction_mode="single",
        options=[
            {"id": "data_breach", "label": "Data Breach"},
            {"id": "ransomware", "label": "Ransomware"},
            {"id": "insider_threat", "label": "Insider Threat"},
            {"id": "ddos", "label": "DDoS Attack"},
            {"id": "malware", "label": "Malware"},
            {"id": "phishing", "label": "Phishing"},
        ],
        state_key="threat_scenario",
        required=False,
    ),
    "persona": ScopingQuestionTemplate(
        filter_name="persona",
        question_id="persona",
        label="Who is the dashboard for?",
        interaction_mode="single",
        options=[
            {"id": "soc_analyst", "label": "SOC Analyst"},
            {"id": "security_manager", "label": "Security Manager"},
            {"id": "ciso", "label": "CISO"},
            {"id": "compliance_officer", "label": "Compliance Officer"},
        ],
        state_key="persona",
        required=False,
    ),
}
