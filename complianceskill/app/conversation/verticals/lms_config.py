"""
LMS / CSOD Vertical Conversation Configuration

Defines scoping question templates and conversation config for LMS vertical.
"""
from app.conversation.config import ScopingQuestionTemplate, VerticalConversationConfig

# LMS Scoping Question Templates
# These 8 templates cover all filter_names used by recommendation areas
LMS_SCOPING_TEMPLATES = {
    "org_unit": ScopingQuestionTemplate(
        filter_name="org_unit",
        question_id="org_unit",
        label="Which part of the organisation should I focus on?",
        interaction_mode="single",
        options=[
            {"id": "whole_org", "label": "The whole organisation"},
            {"id": "department", "label": "A specific department or region"},
            {"id": "role", "label": "A specific role or job family"},
            {"id": "manager", "label": "Direct reports under a particular manager"},
        ],
        state_key="org_unit",
        required=False,
    ),
    "time_period": ScopingQuestionTemplate(
        filter_name="time_period",
        question_id="time_period",
        label="What time window matters most to you?",
        interaction_mode="single",
        options=[
            {"id": "last_30d", "label": "Last 30 days"},
            {"id": "last_quarter", "label": "Last quarter"},
            {"id": "ytd", "label": "Year to date"},
            {"id": "yoy", "label": "Comparing this year to last year"},
        ],
        state_key="time_window",
        required=False,
    ),
    "due_date_range": ScopingQuestionTemplate(
        filter_name="due_date_range",
        question_id="due_date_range",
        label="Which deadline window are you most concerned about?",
        interaction_mode="single",
        options=[
            {"id": "next_30d", "label": "Next 30 days"},
            {"id": "next_60d", "label": "Next 60 days"},
            {"id": "next_90d", "label": "Next 90 days"},
            {"id": "overdue", "label": "Already overdue"},
        ],
        state_key="deadline_window",
        required=False,
    ),
    "training_type": ScopingQuestionTemplate(
        filter_name="training_type",
        question_id="training_type",
        label="What kind of training are you most concerned about?",
        interaction_mode="single",
        options=[
            {"id": "mandatory", "label": "Mandatory regulatory compliance training"},
            {"id": "certification", "label": "Certifications with expiry dates"},
            {"id": "all", "label": "All assigned training in general"},
            {"id": "unsure", "label": "I'm not sure"},
        ],
        state_key="training_type",
        required=False,
    ),
    "delivery_method": ScopingQuestionTemplate(
        filter_name="delivery_method",
        question_id="delivery_method",
        label="Which delivery method do you want to focus on?",
        interaction_mode="single",
        options=[
            {"id": "ilt", "label": "Instructor-led training (ILT)"},
            {"id": "self_directed", "label": "Self-directed online learning"},
            {"id": "blended", "label": "Blended learning"},
            {"id": "all", "label": "All delivery methods"},
        ],
        state_key="delivery_method",
        required=False,
    ),
    "audit_window": ScopingQuestionTemplate(
        filter_name="audit_window",
        question_id="audit_window",
        label="When is the audit?",
        interaction_mode="single",
        options=[
            {"id": "next_30d", "label": "Next 30 days"},
            {"id": "next_60d", "label": "Next 60 days"},
            {"id": "next_90d", "label": "Next 90 days"},
            {"id": "past", "label": "Already passed"},
        ],
        state_key="audit_window",
        required=False,
    ),
    "course_id": ScopingQuestionTemplate(
        filter_name="course_id",
        question_id="course_id",
        label="Do you want to focus on a specific course or programme?",
        interaction_mode="single",
        options=[
            {"id": "yes_specific", "label": "Yes, a specific course"},
            {"id": "yes_programme", "label": "Yes, a specific programme"},
            {"id": "no", "label": "No, all courses"},
        ],
        state_key="course_scope",
        required=False,
    ),
    "user_status": ScopingQuestionTemplate(
        filter_name="user_status",
        question_id="user_status",
        label="Which learner population should I include?",
        interaction_mode="multi",  # Multi-select
        options=[
            {"id": "active", "label": "Active learners"},
            {"id": "inactive", "label": "Inactive learners"},
            {"id": "at_risk", "label": "At-risk learners"},
            {"id": "overdue", "label": "Overdue learners"},
        ],
        state_key="user_status",
        required=False,
    ),
}

# LMS Conversation Configuration
LMS_CONVERSATION_CONFIG = VerticalConversationConfig(
    vertical_id="lms",
    display_name="LMS Intelligence",
    l1_collection="csod_l1_source_concepts",  # Maps to MDLCollections.CSOD_L1_SOURCE_CONCEPTS
    l2_collection="csod_l2_recommendation_areas",  # Maps to MDLCollections.CSOD_L2_RECOMMENDATION_AREAS
    supported_datasources=[
        {
            "id": "cornerstone",
            "display_name": "Cornerstone OnDemand",
            "description": "LMS platform — training, compliance, assessments, ILT",
        },
        # Add more as integrations are built
    ],
    scoping_question_templates=LMS_SCOPING_TEMPLATES,
    always_include_filters=["org_unit", "time_period"],  # Always ask these
    intent_to_workflow={
        "metrics_dashboard_plan": "csod_workflow",
        "metrics_recommender_with_gold_plan": "csod_workflow",
        "dashboard_generation_for_persona": "csod_workflow",
        "compliance_test_generator": "csod_workflow",
        "metric_kpi_advisor": "csod_metric_advisor_workflow",
    },
    default_workflow="csod_workflow",
    max_scoping_questions_per_turn=3,
)
