"""
Domain Configuration for Feature Engineering Agents

This module provides domain-specific configurations that allow the feature engineering
agents to work across different domains (cybersecurity, HR compliance, learning, risk, etc.)
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass
from enum import Enum


class DomainFeaturePattern(BaseModel):
    """Configuration for a feature pattern template"""
    template: str = Field(description="Feature name template with placeholders")
    logic: str = Field(description="SQL-like pseudocode for the feature calculation")
    schemas: List[str] = Field(default_factory=list, description="Required schema names")
    description: str = Field(default="", description="Description of the feature pattern")


class DomainCategoryMapping(BaseModel):
    """Mapping of query keywords to knowledge categories"""
    keywords: List[str] = Field(description="Keywords that trigger this category")
    category: str = Field(description="Knowledge category name")
    description: str = Field(default="", description="Description of the category")


class MetricType(str, Enum):
    """Types of compliance metrics"""
    COUNT = "count"
    RATE = "rate"
    PERCENTAGE = "percentage"
    AVERAGE = "average"
    TREND = "trend"
    RISK_SCORE = "risk_score"
    FORECAST = "forecast"
    DISTRIBUTION = "distribution"


class ComplianceMetricQuestion(BaseModel):
    """A natural language question that maps to a compliance metric"""
    question: str = Field(description="Natural language question about compliance")
    metric_name: str = Field(description="Canonical name for the metric")
    metric_type: MetricType = Field(description="Type of metric")
    description: str = Field(description="Description of what the metric measures")
    related_questions: List[str] = Field(
        default_factory=list,
        description="Alternative phrasings of the same question"
    )
    required_entities: List[str] = Field(
        default_factory=list,
        description="Entity types required to answer this question (e.g., 'Employee', 'Course')"
    )
    aggregation_levels: List[str] = Field(
        default_factory=list,
        description="Levels at which this metric can be aggregated (e.g., 'Department', 'Location OU')"
    )
    feature_patterns: List[str] = Field(
        default_factory=list,
        description="Feature pattern names that can be used to calculate this metric"
    )
    schemas: List[str] = Field(
        default_factory=list,
        description="Required schema names to calculate this metric"
    )
    dashboard_section: Optional[str] = Field(
        default=None,
        description="Dashboard section where this metric typically appears"
    )


class ComplianceMetricLibrary(BaseModel):
    """Library of compliance metrics organized by domain"""
    domain_name: str = Field(description="Domain this metric library belongs to")
    domain_description: str = Field(default="", description="Description of the domain")
    metrics: List[ComplianceMetricQuestion] = Field(
        default_factory=list,
        description="List of compliance metric questions for this domain"
    )
    metric_categories: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Categorization of metrics by category (e.g., 'risk_metrics', 'completion_metrics')"
    )
    
    def get_metrics_by_category(self, category: str) -> List[ComplianceMetricQuestion]:
        """Get all metrics in a specific category"""
        metric_names = self.metric_categories.get(category, [])
        return [m for m in self.metrics if m.metric_name in metric_names]
    
    def find_matching_metrics(self, query: str) -> List[ComplianceMetricQuestion]:
        """Find metrics that match a natural language query"""
        query_lower = query.lower()
        matches = []
        for metric in self.metrics:
            # Check if query matches the question or related questions
            if query_lower in metric.question.lower() or metric.question.lower() in query_lower:
                matches.append(metric)
            elif any(query_lower in q.lower() or q.lower() in query_lower for q in metric.related_questions):
                matches.append(metric)
        return matches


class DomainConfiguration(BaseModel):
    """Domain-specific configuration for feature engineering"""
    
    # Domain identification
    domain_name: str = Field(description="Name of the domain (e.g., 'cybersecurity', 'hr_compliance', 'learning')")
    domain_description: str = Field(default="", description="Description of the domain")
    
    # Domain-specific terminology
    entity_types: List[str] = Field(default_factory=list, description="Types of entities in this domain (e.g., 'Asset', 'CVE', 'Employee', 'Course')")
    severity_levels: List[str] = Field(default_factory=list, description="Severity/priority levels (e.g., 'Critical', 'High', 'Medium', 'Low')")
    time_constraint_terms: List[str] = Field(default_factory=list, description="Terms for time constraints (e.g., 'SLA', 'deadline', 'due_date')")
    
    # Compliance frameworks
    compliance_frameworks: List[str] = Field(default_factory=list, description="Supported compliance frameworks (e.g., 'SOC2', 'PCI-DSS', 'HIPAA', 'GDPR')")
    
    # Feature patterns
    feature_patterns: Dict[str, DomainFeaturePattern] = Field(
        default_factory=dict,
        description="Feature pattern templates for this domain"
    )
    
    # Knowledge category mappings
    category_mappings: List[DomainCategoryMapping] = Field(
        default_factory=list,
        description="Mappings from query keywords to knowledge categories"
    )
    
    # System prompts customization
    query_understanding_prompt: str = Field(
        default="",
        description="Custom prompt for query understanding (if empty, uses default)"
    )
    feature_recommendation_prompt: str = Field(
        default="",
        description="Custom prompt for feature recommendation (if empty, uses default)"
    )
    
    # Default context values
    default_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default context values (e.g., SLA definitions, common thresholds)"
    )
    
    # Aggregation levels
    aggregation_levels: List[str] = Field(
        default_factory=list,
        description="Common aggregation levels (e.g., 'Asset', 'Repository', 'Department', 'Team')"
    )


# Predefined domain configurations
CYBERSECURITY_DOMAIN_CONFIG = DomainConfiguration(
    domain_name="cybersecurity",
    domain_description="Cybersecurity and vulnerability management domain",
    entity_types=["Asset", "CVE", "Vulnerability", "Software", "Patch", "Repository"],
    severity_levels=["Critical", "High", "Medium", "Low"],
    time_constraint_terms=["SLA", "remediation_time", "detected_time", "patch_time"],
    compliance_frameworks=["SOC2", "PCI-DSS", "HIPAA"],
    feature_patterns={
        "sla_compliance": DomainFeaturePattern(
            template="{severity}_sla_breached_count",
            logic="Count vulnerabilities where (current_date - detected_time) > {sla_days}",
            schemas=["vulnerability_instances", "cve"],
            description="SLA compliance tracking for vulnerabilities"
        ),
        "exploitability": DomainFeaturePattern(
            template="{severity}_exploitable_count",
            logic="Count vulnerabilities where epssScore > threshold OR cisaExploited = true",
            schemas=["vulnerability_instances", "cve"],
            description="Exploitability assessment features"
        ),
        "risk_metrics": DomainFeaturePattern(
            template="avg_{risk_type}_risk",
            logic="Average of effective_risk/raw_risk per asset/cve",
            schemas=["features", "asset"],
            description="Risk scoring metrics"
        ),
        "patch_lag": DomainFeaturePattern(
            template="avg_patch_lag_days",
            logic="Average (latest_available_patch_release_time - latest_installed_patch_release_time)",
            schemas=["software_instances"],
            description="Patch deployment lag metrics"
        ),
        "time_to_remediation": DomainFeaturePattern(
            template="avg_remediation_time_{severity}",
            logic="Average (remediation_time - detected_time) WHERE state = 'remediated'",
            schemas=["vulnerability_instances"],
            description="Time to remediation metrics"
        )
    },
    category_mappings=[
        DomainCategoryMapping(
            keywords=["sla", "remediation", "time", "deadline"],
            category="sla_compliance",
            description="SLA and time-based compliance metrics"
        ),
        DomainCategoryMapping(
            keywords=["exploit", "epss", "cisa", "reachability", "exploitable"],
            category="exploitability",
            description="Exploitability and security risk metrics"
        ),
        DomainCategoryMapping(
            keywords=["risk", "criticality", "impact", "severity"],
            category="risk_metrics",
            description="Risk assessment and scoring metrics"
        ),
        DomainCategoryMapping(
            keywords=["compliance", "soc2", "pci", "hipaa", "audit"],
            category="compliance",
            description="Compliance framework requirements"
        )
    ],
    aggregation_levels=["Asset", "CVE", "Repository", "Software", "Department"],
    default_context={
        "critical_sla_days": 7,
        "high_sla_days": 30,
        "medium_sla_days": 90,
        "time_measured_from": "detected_time",
        "exploitability_uses_reachability": True,
        "features_are_time_series": True
    }
)


HR_COMPLIANCE_DOMAIN_CONFIG = DomainConfiguration(
    domain_name="hr_compliance",
    domain_description="Human Resources compliance and learning management domain",
    entity_types=["Employee", "Course", "Training", "Certification", "Department", "Role"],
    severity_levels=["Critical", "High", "Medium", "Low"],
    time_constraint_terms=["deadline", "due_date", "expiry", "completion_date", "enrollment_date"],
    compliance_frameworks=["GDPR", "SOC2", "HIPAA", "ISO27001"],
    feature_patterns={
        "training_completion": DomainFeaturePattern(
            template="{training_type}_completion_rate",
            logic="Percentage of employees who completed training within deadline",
            schemas=["training_instances", "employee"],
            description="Training completion tracking"
        ),
        "certification_expiry": DomainFeaturePattern(
            template="expiring_certifications_count",
            logic="Count certifications expiring within {days} days",
            schemas=["certifications", "employee"],
            description="Certification expiry tracking"
        ),
        "compliance_gap": DomainFeaturePattern(
            template="{compliance_type}_gap_count",
            logic="Count employees missing required training/certifications",
            schemas=["employee", "training_instances", "certifications"],
            description="Compliance gap identification"
        ),
        "learning_progress": DomainFeaturePattern(
            template="avg_learning_progress_{course_type}",
            logic="Average progress percentage for course type",
            schemas=["learning_instances", "course"],
            description="Learning progress metrics"
        )
    },
    category_mappings=[
        DomainCategoryMapping(
            keywords=["deadline", "due_date", "expiry", "completion"],
            category="deadline_compliance",
            description="Deadline and completion tracking"
        ),
        DomainCategoryMapping(
            keywords=["training", "course", "learning", "certification"],
            category="learning_metrics",
            description="Learning and training metrics"
        ),
        DomainCategoryMapping(
            keywords=["compliance", "gap", "requirement", "mandatory"],
            category="compliance",
            description="Compliance requirement tracking"
        )
    ],
    aggregation_levels=["Employee", "Department", "Role", "Course", "Training"],
    default_context={
        "critical_deadline_days": 7,
        "high_deadline_days": 30,
        "medium_deadline_days": 90,
        "time_measured_from": "enrollment_date",
        "completion_threshold": 100,
        "features_are_time_series": True
    }
)


RISK_MANAGEMENT_DOMAIN_CONFIG = DomainConfiguration(
    domain_name="risk_management",
    domain_description="Risk management and assessment domain",
    entity_types=["Risk", "Control", "Assessment", "Finding", "Mitigation"],
    severity_levels=["Critical", "High", "Medium", "Low"],
    time_constraint_terms=["assessment_date", "mitigation_deadline", "review_date"],
    compliance_frameworks=["COSO", "ISO31000", "NIST"],
    feature_patterns={
        "risk_score": DomainFeaturePattern(
            template="aggregated_risk_score_{dimension}",
            logic="Weighted average of risk scores by dimension",
            schemas=["risk_assessments", "controls"],
            description="Aggregated risk scoring"
        ),
        "control_effectiveness": DomainFeaturePattern(
            template="control_effectiveness_rate",
            logic="Percentage of controls meeting effectiveness criteria",
            schemas=["controls", "assessments"],
            description="Control effectiveness metrics"
        ),
        "mitigation_progress": DomainFeaturePattern(
            template="mitigation_progress_{risk_level}",
            logic="Percentage of risks with mitigation plans in progress",
            schemas=["risks", "mitigations"],
            description="Mitigation progress tracking"
        )
    },
    category_mappings=[
        DomainCategoryMapping(
            keywords=["risk", "score", "assessment", "likelihood", "impact"],
            category="risk_metrics",
            description="Risk assessment and scoring"
        ),
        DomainCategoryMapping(
            keywords=["control", "effectiveness", "compliance"],
            category="control_metrics",
            description="Control effectiveness metrics"
        ),
        DomainCategoryMapping(
            keywords=["mitigation", "remediation", "action"],
            category="mitigation_metrics",
            description="Mitigation and remediation tracking"
        )
    ],
    aggregation_levels=["Risk", "Control", "Department", "Business_Unit", "Process"],
    default_context={
        "risk_score_range": "0-100",
        "effectiveness_threshold": 80,
        "mitigation_deadline_buffer_days": 30,
        "features_are_time_series": True
    }
)


# Domain configuration registry
DOMAIN_CONFIGS: Dict[str, DomainConfiguration] = {
    "cybersecurity": CYBERSECURITY_DOMAIN_CONFIG,
    "hr_compliance": HR_COMPLIANCE_DOMAIN_CONFIG,
    "risk_management": RISK_MANAGEMENT_DOMAIN_CONFIG,
}


def get_domain_config(domain_name: str) -> DomainConfiguration:
    """Get domain configuration by name"""
    if domain_name not in DOMAIN_CONFIGS:
        raise ValueError(f"Unknown domain: {domain_name}. Available domains: {list(DOMAIN_CONFIGS.keys())}")
    return DOMAIN_CONFIGS[domain_name]


def create_custom_domain_config(
    domain_name: str,
    domain_description: str = "",
    entity_types: Optional[List[str]] = None,
    severity_levels: Optional[List[str]] = None,
    compliance_frameworks: Optional[List[str]] = None,
    feature_patterns: Optional[Dict[str, DomainFeaturePattern]] = None,
    category_mappings: Optional[List[DomainCategoryMapping]] = None,
    aggregation_levels: Optional[List[str]] = None,
    default_context: Optional[Dict[str, Any]] = None
) -> DomainConfiguration:
    """Create a custom domain configuration"""
    return DomainConfiguration(
        domain_name=domain_name,
        domain_description=domain_description,
        entity_types=entity_types or [],
        severity_levels=severity_levels or [],
        compliance_frameworks=compliance_frameworks or [],
        feature_patterns=feature_patterns or {},
        category_mappings=category_mappings or [],
        aggregation_levels=aggregation_levels or [],
        default_context=default_context or {}
    )


# ============================================================================
# COMPLIANCE METRICS LIBRARIES
# ============================================================================

HR_COMPLIANCE_METRICS = ComplianceMetricLibrary(
    domain_name="hr_compliance",
    domain_description="HR compliance and learning management metrics library",
    metrics=[
        # Compliance Control Dashboard Metrics
        ComplianceMetricQuestion(
            question="How many registrations are at risk of not completing training on time?",
            metric_name="registrations_at_risk",
            metric_type=MetricType.COUNT,
            description="Total number of registered users who are at risk for not completing training on time",
            related_questions=[
                "What is the total number of registrations at risk?",
                "How many learning object registrations are at risk?",
                "Count of registrations at risk for on-time completion"
            ],
            required_entities=["Employee", "Course", "Training"],
            aggregation_levels=["Location OU", "Department OU", "Course", "Training"],
            feature_patterns=["training_completion", "compliance_gap"],
            schemas=["training_instances", "employee", "course"],
            dashboard_section="Registrations at Risk"
        ),
        ComplianceMetricQuestion(
            question="How many employees are at risk of not completing training on time?",
            metric_name="employees_at_risk",
            metric_type=MetricType.COUNT,
            description="Total number of individual employees who are at risk for not completing training on time",
            related_questions=[
                "What is the total number of employees at risk?",
                "How many users are at risk?",
                "Count of employees at risk for on-time completion"
            ],
            required_entities=["Employee", "Course", "Training"],
            aggregation_levels=["Location OU", "Department OU", "Role", "Position OU"],
            feature_patterns=["training_completion", "compliance_gap"],
            schemas=["training_instances", "employee", "course"],
            dashboard_section="Employees at Risk"
        ),
        ComplianceMetricQuestion(
            question="What are the primary risk factors causing training completion risk?",
            metric_name="primary_risk_factors",
            metric_type=MetricType.DISTRIBUTION,
            description="Distribution of the top primary risk factors for all trainings that are at risk",
            related_questions=[
                "What factors are causing compliance risk?",
                "What are the main reasons for training completion risk?",
                "Which risk factors are driving non-compliance?",
                "What risk factors impact on-time completion?"
            ],
            required_entities=["Course", "Training"],
            aggregation_levels=["Location OU", "Department OU"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "course"],
            dashboard_section="Primary Risk Factors"
        ),
        ComplianceMetricQuestion(
            question="How many learning objects are at risk by department?",
            metric_name="los_at_risk_by_department",
            metric_type=MetricType.COUNT,
            description="Number of learning objects at risk within each Department OU",
            related_questions=[
                "Which departments have the most learning objects at risk?",
                "What is the distribution of at-risk learning objects by department?",
                "How many courses are at risk per department?"
            ],
            required_entities=["Course", "Department"],
            aggregation_levels=["Department OU", "Location OU"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "course", "employee"],
            dashboard_section="Registrations at Risk"
        ),
        ComplianceMetricQuestion(
            question="How many employees are at risk by department?",
            metric_name="employees_at_risk_by_department",
            metric_type=MetricType.COUNT,
            description="Number of employees at risk within each Department OU",
            related_questions=[
                "Which departments have the most employees at risk?",
                "What is the distribution of at-risk employees by department?",
                "How many users are at risk per department?"
            ],
            required_entities=["Employee", "Department"],
            aggregation_levels=["Department OU", "Location OU"],
            feature_patterns=["training_completion", "compliance_gap"],
            schemas=["training_instances", "employee"],
            dashboard_section="Employees at Risk"
        ),
        ComplianceMetricQuestion(
            question="How many learning objects are at risk for a specific employee?",
            metric_name="los_at_risk_per_employee",
            metric_type=MetricType.COUNT,
            description="Number of learning objects at risk for a specific employee",
            related_questions=[
                "How many courses is an employee at risk for?",
                "What is the count of at-risk learning objects per employee?",
                "How many trainings are at risk for this employee?"
            ],
            required_entities=["Employee", "Course"],
            aggregation_levels=["Employee"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "employee", "course"],
            dashboard_section="Employees at Risk"
        ),
        ComplianceMetricQuestion(
            question="How many users are at risk for a specific learning object?",
            metric_name="users_at_risk_per_lo",
            metric_type=MetricType.COUNT,
            description="Number of users at risk for a specific learning object",
            related_questions=[
                "How many employees are at risk for this course?",
                "What is the count of at-risk users per learning object?",
                "How many users are at risk for this training?"
            ],
            required_entities=["Course", "Employee"],
            aggregation_levels=["Course", "Training"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "course", "employee"],
            dashboard_section="Registrations at Risk"
        ),
        
        # Compliance Guide Dashboard Metrics
        ComplianceMetricQuestion(
            question="What is the historic compliance rate?",
            metric_name="historic_compliance_rate",
            metric_type=MetricType.RATE,
            description="Historic compliance rate over a specified time period (typically 1 year, divided quarterly)",
            related_questions=[
                "What is the historical compliance rate?",
                "What was the compliance rate in the past?",
                "What is the trend of compliance rates over time?",
                "How has compliance rate changed historically?"
            ],
            required_entities=["Employee", "Course", "Training"],
            aggregation_levels=["Location OU", "Department OU", "Quarter", "Year"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "employee", "course"],
            dashboard_section="Compliance Rate"
        ),
        ComplianceMetricQuestion(
            question="What is the forecasted compliance rate?",
            metric_name="forecasted_compliance_rate",
            metric_type=MetricType.FORECAST,
            description="Forecasted compliance rate looking ahead, divided quarterly, based on current course registrations due in the future",
            related_questions=[
                "What is the predicted compliance rate?",
                "What will the compliance rate be in the future?",
                "What is the projected compliance rate?",
                "How is compliance rate expected to change?"
            ],
            required_entities=["Employee", "Course", "Training"],
            aggregation_levels=["Location OU", "Department OU", "Quarter", "Year"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "employee", "course"],
            dashboard_section="Compliance Rate"
        ),
        ComplianceMetricQuestion(
            question="What is the compliance rate by organizational unit?",
            metric_name="compliance_rate_by_ou",
            metric_type=MetricType.RATE,
            description="Compliance rate for each organizational unit, color-coded from low (red) to high (green)",
            related_questions=[
                "Which organizational units have the highest compliance rates?",
                "What is the compliance rate for each department?",
                "How does compliance rate vary by organizational unit?",
                "Which departments are most compliant?"
            ],
            required_entities=["Employee", "Department"],
            aggregation_levels=["Location OU", "Department OU"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "employee"],
            dashboard_section="Compliance Rate by Organizational Unit"
        ),
        ComplianceMetricQuestion(
            question="How many courses are overdue for completion by department?",
            metric_name="overdue_courses_by_department",
            metric_type=MetricType.COUNT,
            description="Number of courses that are overdue for completion within each department",
            related_questions=[
                "How many overdue courses does each department have?",
                "What is the count of overdue trainings by department?",
                "Which departments have the most overdue courses?"
            ],
            required_entities=["Course", "Department"],
            aggregation_levels=["Department OU", "Location OU"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "course", "employee"],
            dashboard_section="Compliance Rate by Organizational Unit"
        ),
        ComplianceMetricQuestion(
            question="What predictive factors contribute to on-time course completion?",
            metric_name="predictive_factors_completion",
            metric_type=MetricType.DISTRIBUTION,
            description="Factors that are predictive to the organization's on-time course completion",
            related_questions=[
                "What factors predict training completion?",
                "Which factors influence on-time completion?",
                "What are the key predictors of compliance?",
                "What factors affect whether employees complete training on time?"
            ],
            required_entities=["Employee", "Course", "Training"],
            aggregation_levels=["Location OU", "Department OU"],
            feature_patterns=["training_completion", "learning_progress"],
            schemas=["training_instances", "employee", "course"],
            dashboard_section="Analyze Predictive Factors"
        ),
        ComplianceMetricQuestion(
            question="What is the training completion rate?",
            metric_name="training_completion_rate",
            metric_type=MetricType.PERCENTAGE,
            description="Percentage of employees who completed training within the deadline",
            related_questions=[
                "What percentage of employees completed training on time?",
                "What is the completion rate for training?",
                "How many employees completed their required training?",
                "What is the on-time completion percentage?"
            ],
            required_entities=["Employee", "Training"],
            aggregation_levels=["Department", "Location OU", "Course", "Training"],
            feature_patterns=["training_completion"],
            schemas=["training_instances", "employee"],
            dashboard_section="Compliance Rate"
        ),
        ComplianceMetricQuestion(
            question="What is the average learning progress for a course type?",
            metric_name="avg_learning_progress",
            metric_type=MetricType.AVERAGE,
            description="Average progress percentage for a specific course type",
            related_questions=[
                "What is the average progress for this type of course?",
                "How far along are employees in this course type?",
                "What is the mean learning progress?",
                "What is the average completion percentage for this course type?"
            ],
            required_entities=["Course", "Employee"],
            aggregation_levels=["Course", "Training", "Department"],
            feature_patterns=["learning_progress"],
            schemas=["learning_instances", "course"],
            dashboard_section="Details"
        ),
        ComplianceMetricQuestion(
            question="How many certifications are expiring soon?",
            metric_name="expiring_certifications_count",
            metric_type=MetricType.COUNT,
            description="Count of certifications expiring within a specified number of days",
            related_questions=[
                "How many certifications will expire in the next X days?",
                "What certifications are about to expire?",
                "How many employees have expiring certifications?",
                "What is the count of certifications expiring soon?"
            ],
            required_entities=["Employee", "Certification"],
            aggregation_levels=["Department", "Location OU", "Certification"],
            feature_patterns=["certification_expiry"],
            schemas=["certifications", "employee"],
            dashboard_section="Details"
        ),
        ComplianceMetricQuestion(
            question="How many employees are missing required training?",
            metric_name="compliance_gap_count",
            metric_type=MetricType.COUNT,
            description="Count of employees missing required training or certifications",
            related_questions=[
                "How many employees have compliance gaps?",
                "What is the count of employees missing mandatory training?",
                "How many users are non-compliant?",
                "What is the number of employees with training gaps?"
            ],
            required_entities=["Employee", "Training", "Certification"],
            aggregation_levels=["Department", "Location OU", "Role"],
            feature_patterns=["compliance_gap"],
            schemas=["employee", "training_instances", "certifications"],
            dashboard_section="Compliance Gap"
        ),
    ],
    metric_categories={
        "risk_metrics": [
            "registrations_at_risk",
            "employees_at_risk",
            "primary_risk_factors",
            "los_at_risk_by_department",
            "employees_at_risk_by_department"
        ],
        "completion_metrics": [
            "training_completion_rate",
            "historic_compliance_rate",
            "forecasted_compliance_rate",
            "compliance_rate_by_ou"
        ],
        "progress_metrics": [
            "avg_learning_progress",
            "los_at_risk_per_employee",
            "users_at_risk_per_lo"
        ],
        "expiry_metrics": [
            "expiring_certifications_count"
        ],
        "gap_metrics": [
            "compliance_gap_count",
            "overdue_courses_by_department"
        ],
        "predictive_metrics": [
            "predictive_factors_completion"
        ]
    }
)


CYBERSECURITY_COMPLIANCE_METRICS = ComplianceMetricLibrary(
    domain_name="cybersecurity",
    domain_description="Cybersecurity compliance metrics library",
    metrics=[
        ComplianceMetricQuestion(
            question="How many vulnerabilities have breached SLA?",
            metric_name="sla_breached_count",
            metric_type=MetricType.COUNT,
            description="Count of vulnerabilities where remediation time exceeds SLA requirements",
            related_questions=[
                "How many vulnerabilities are past their SLA deadline?",
                "What is the count of SLA breaches?",
                "How many vulnerabilities exceeded their remediation SLA?",
                "What vulnerabilities are out of SLA compliance?"
            ],
            required_entities=["Vulnerability", "CVE"],
            aggregation_levels=["Asset", "Repository", "Severity", "Department"],
            feature_patterns=["sla_compliance"],
            schemas=["vulnerability_instances", "cve"],
            dashboard_section="SLA Compliance"
        ),
        ComplianceMetricQuestion(
            question="What is the average time to remediation?",
            metric_name="avg_remediation_time",
            metric_type=MetricType.AVERAGE,
            description="Average time from detection to remediation for vulnerabilities",
            related_questions=[
                "What is the mean time to remediate vulnerabilities?",
                "How long does it take on average to fix vulnerabilities?",
                "What is the average remediation duration?",
                "How long are vulnerabilities open on average?"
            ],
            required_entities=["Vulnerability"],
            aggregation_levels=["Asset", "Severity", "Department"],
            feature_patterns=["time_to_remediation"],
            schemas=["vulnerability_instances"],
            dashboard_section="Remediation Metrics"
        ),
        ComplianceMetricQuestion(
            question="How many exploitable vulnerabilities exist?",
            metric_name="exploitable_vulnerabilities_count",
            metric_type=MetricType.COUNT,
            description="Count of vulnerabilities that are exploitable (high EPSS score or CISA exploited)",
            related_questions=[
                "How many vulnerabilities can be exploited?",
                "What is the count of exploitable CVEs?",
                "How many vulnerabilities are actively exploitable?",
                "What vulnerabilities have high exploitability scores?"
            ],
            required_entities=["Vulnerability", "CVE"],
            aggregation_levels=["Asset", "Severity", "Repository"],
            feature_patterns=["exploitability"],
            schemas=["vulnerability_instances", "cve"],
            dashboard_section="Exploitability"
        ),
        ComplianceMetricQuestion(
            question="What is the average patch lag?",
            metric_name="avg_patch_lag_days",
            metric_type=MetricType.AVERAGE,
            description="Average number of days between patch availability and installation",
            related_questions=[
                "How long does it take to deploy patches after they're available?",
                "What is the average delay in patch deployment?",
                "What is the mean patch lag time?",
                "How many days on average before patches are installed?"
            ],
            required_entities=["Software", "Patch"],
            aggregation_levels=["Software", "Repository", "Department"],
            feature_patterns=["patch_lag"],
            schemas=["software_instances"],
            dashboard_section="Patch Management"
        ),
        ComplianceMetricQuestion(
            question="What is the average risk score?",
            metric_name="avg_risk_score",
            metric_type=MetricType.AVERAGE,
            description="Average risk score across assets or vulnerabilities",
            related_questions=[
                "What is the mean risk score?",
                "What is the average effective risk?",
                "What is the overall risk level?",
                "What is the average risk rating?"
            ],
            required_entities=["Asset", "Vulnerability"],
            aggregation_levels=["Asset", "CVE", "Repository", "Department"],
            feature_patterns=["risk_metrics"],
            schemas=["features", "asset"],
            dashboard_section="Risk Assessment"
        ),
    ],
    metric_categories={
        "sla_metrics": ["sla_breached_count", "avg_remediation_time"],
        "exploitability_metrics": ["exploitable_vulnerabilities_count"],
        "patch_metrics": ["avg_patch_lag_days"],
        "risk_metrics": ["avg_risk_score"]
    }
)


RISK_MANAGEMENT_COMPLIANCE_METRICS = ComplianceMetricLibrary(
    domain_name="risk_management",
    domain_description="Risk management compliance metrics library",
    metrics=[
        ComplianceMetricQuestion(
            question="What is the aggregated risk score?",
            metric_name="aggregated_risk_score",
            metric_type=MetricType.RISK_SCORE,
            description="Weighted average of risk scores by dimension",
            related_questions=[
                "What is the overall risk score?",
                "What is the total risk assessment?",
                "What is the combined risk score?",
                "What is the enterprise risk level?"
            ],
            required_entities=["Risk", "Control"],
            aggregation_levels=["Department", "Business_Unit", "Process"],
            feature_patterns=["risk_score"],
            schemas=["risk_assessments", "controls"],
            dashboard_section="Risk Assessment"
        ),
        ComplianceMetricQuestion(
            question="What is the control effectiveness rate?",
            metric_name="control_effectiveness_rate",
            metric_type=MetricType.PERCENTAGE,
            description="Percentage of controls meeting effectiveness criteria",
            related_questions=[
                "What percentage of controls are effective?",
                "How effective are our controls?",
                "What is the control effectiveness percentage?",
                "How many controls are working as intended?"
            ],
            required_entities=["Control"],
            aggregation_levels=["Department", "Business_Unit", "Process"],
            feature_patterns=["control_effectiveness"],
            schemas=["controls", "assessments"],
            dashboard_section="Control Effectiveness"
        ),
        ComplianceMetricQuestion(
            question="What is the mitigation progress?",
            metric_name="mitigation_progress",
            metric_type=MetricType.PERCENTAGE,
            description="Percentage of risks with mitigation plans in progress",
            related_questions=[
                "What percentage of risks have mitigation plans?",
                "How many risks are being mitigated?",
                "What is the progress on risk mitigation?",
                "How many mitigation plans are active?"
            ],
            required_entities=["Risk", "Mitigation"],
            aggregation_levels=["Risk", "Department", "Business_Unit"],
            feature_patterns=["mitigation_progress"],
            schemas=["risks", "mitigations"],
            dashboard_section="Mitigation Tracking"
        ),
    ],
    metric_categories={
        "risk_metrics": ["aggregated_risk_score"],
        "control_metrics": ["control_effectiveness_rate"],
        "mitigation_metrics": ["mitigation_progress"]
    }
)


# Compliance metrics library registry
COMPLIANCE_METRIC_LIBRARIES: Dict[str, ComplianceMetricLibrary] = {
    "hr_compliance": HR_COMPLIANCE_METRICS,
    "cybersecurity": CYBERSECURITY_COMPLIANCE_METRICS,
    "risk_management": RISK_MANAGEMENT_COMPLIANCE_METRICS,
}


def get_compliance_metric_library(domain_name: str) -> ComplianceMetricLibrary:
    """Get compliance metric library by domain name"""
    if domain_name not in COMPLIANCE_METRIC_LIBRARIES:
        raise ValueError(
            f"Unknown domain: {domain_name}. "
            f"Available domains: {list(COMPLIANCE_METRIC_LIBRARIES.keys())}"
        )
    return COMPLIANCE_METRIC_LIBRARIES[domain_name]


def find_metric_by_question(query: str, domain_name: Optional[str] = None) -> List[ComplianceMetricQuestion]:
    """Find compliance metrics that match a natural language query
    
    Args:
        query: Natural language question or query
        domain_name: Optional domain name to search within. If None, searches all domains.
    
    Returns:
        List of matching ComplianceMetricQuestion objects
    """
    if domain_name:
        library = get_compliance_metric_library(domain_name)
        return library.find_matching_metrics(query)
    else:
        # Search across all domains
        all_matches = []
        for library in COMPLIANCE_METRIC_LIBRARIES.values():
            matches = library.find_matching_metrics(query)
            all_matches.extend(matches)
        return all_matches


# ============================================================================
# COMPLIANCE CONTROL SETS
# ============================================================================

class ComplianceControl(BaseModel):
    """A compliance control definition"""
    control_id: str = Field(description="Unique control identifier (e.g., 'CC6.1', 'HR-TRAIN-001')")
    control_name: str = Field(description="Name of the control")
    description: str = Field(description="Description of what the control requires")
    framework: str = Field(description="Compliance framework (e.g., 'SOC2', 'HIPAA', 'GDPR')")
    category: str = Field(description="Control category (e.g., 'Access Control', 'Training Compliance')")
    data_support: str = Field(description="How available data can answer/monitor this control")
    confidence: str = Field(default="medium", description="Confidence level: high, medium, or low")
    suggested_features: List[str] = Field(
        default_factory=list,
        description="Suggested features/metrics that support this control"
    )
    required_entities: List[str] = Field(
        default_factory=list,
        description="Entity types required to monitor this control"
    )
    required_schemas: List[str] = Field(
        default_factory=list,
        description="Required schema names to monitor this control"
    )
    related_metrics: List[str] = Field(
        default_factory=list,
        description="Related metric names from the compliance metrics library"
    )


class ComplianceControlSet(BaseModel):
    """A set of compliance controls for a domain"""
    domain_name: str = Field(description="Domain this control set belongs to")
    framework: str = Field(description="Primary compliance framework")
    controls: List[ComplianceControl] = Field(
        default_factory=list,
        description="List of controls in this set"
    )
    control_categories: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Categorization of controls by category"
    )
    
    def get_controls_by_category(self, category: str) -> List[ComplianceControl]:
        """Get all controls in a specific category"""
        control_ids = self.control_categories.get(category, [])
        return [c for c in self.controls if c.control_id in control_ids]
    
    def find_controls_by_keyword(self, keyword: str) -> List[ComplianceControl]:
        """Find controls that match a keyword"""
        keyword_lower = keyword.lower()
        matches = []
        for control in self.controls:
            if (keyword_lower in control.control_name.lower() or
                keyword_lower in control.description.lower() or
                keyword_lower in control.category.lower()):
                matches.append(control)
        return matches


# Cybersecurity Domain Controls (SOC2, PCI-DSS, HIPAA)
CYBERSECURITY_CONTROLS = ComplianceControlSet(
    domain_name="cybersecurity",
    framework="SOC2",
    controls=[
        # CC6: Logical and Physical Access Controls
        ComplianceControl(
            control_id="CC6.1",
            control_name="Logical Access Security Software, Infrastructure, and Overlay Architectures",
            description="The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events to meet the entity's objectives",
            framework="SOC2",
            category="Logical and Physical Access Controls",
            data_support="Vulnerability scan data, asset inventory, and security configuration data can demonstrate logical access controls are implemented",
            confidence="high",
            suggested_features=[
                "vulnerability_count_by_severity",
                "assets_with_security_controls_count",
                "security_configuration_compliance_rate"
            ],
            required_entities=["Asset", "Vulnerability", "Software"],
            required_schemas=["vulnerability_instances", "asset", "software_instances"],
            related_metrics=["sla_breached_count", "exploitable_vulnerabilities_count"]
        ),
        ComplianceControl(
            control_id="CC6.2",
            control_name="Prior to Issuing System Credentials and Granting System Access",
            description="Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users whose access is administered by the entity",
            framework="SOC2",
            category="Logical and Physical Access Controls",
            data_support="User access logs, identity management data, and access request records can demonstrate user registration and authorization processes",
            confidence="high",
            suggested_features=[
                "new_user_registration_count",
                "unauthorized_access_attempts_count",
                "access_request_approval_rate"
            ],
            required_entities=["Employee", "User"],
            required_schemas=["access_logs", "identity_management"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="CC6.3",
            control_name="The Entity Authorizes, Modifies, or Removes Access to Data, Software, Functions, and Other Protected Information Assets",
            description="The entity authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or the system design and changes, giving consideration to the concepts of least privilege and segregation of duties",
            framework="SOC2",
            category="Logical and Physical Access Controls",
            data_support="Access control lists, role assignments, and access modification logs can demonstrate authorization processes",
            confidence="high",
            suggested_features=[
                "access_modification_count",
                "privilege_escalation_count",
                "segregation_of_duties_violations_count"
            ],
            required_entities=["User", "Role"],
            required_schemas=["access_controls", "role_assignments"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="CC6.6",
            control_name="The Entity Restricts Physical Access to Facilities and Protected Information Assets",
            description="The entity restricts physical access to facilities and protected information assets (for example, data center, computer room, media storage) to authorized personnel to meet the entity's objectives",
            framework="SOC2",
            category="Logical and Physical Access Controls",
            data_support="Physical access logs, badge reader data, and facility access records can demonstrate physical access restrictions",
            confidence="medium",
            suggested_features=[
                "unauthorized_physical_access_attempts_count",
                "facility_access_compliance_rate"
            ],
            required_entities=["Facility", "Access"],
            required_schemas=["physical_access_logs"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="CC6.7",
            control_name="The Entity Disables or Removes Access to Protected Information Assets",
            description="The entity disables or removes access to protected information assets when access is no longer required or authorized",
            framework="SOC2",
            category="Logical and Physical Access Controls",
            data_support="Access termination logs, user deprovisioning records, and inactive account data can demonstrate timely access removal",
            confidence="high",
            suggested_features=[
                "stale_account_count",
                "access_removal_lag_days",
                "deprovisioning_compliance_rate"
            ],
            required_entities=["User", "Account"],
            required_schemas=["access_logs", "user_accounts"],
            related_metrics=[]
        ),
        
        # CC7: System Operations
        ComplianceControl(
            control_id="CC7.1",
            control_name="The Entity Uses Detection and Monitoring Procedures to Identify",
            description="The entity uses detection and monitoring procedures to identify (1) changes to configurations that result in the introduction of new vulnerabilities, or (2) susceptibilities to newly discovered vulnerabilities",
            framework="SOC2",
            category="System Operations",
            data_support="Vulnerability scan results, configuration change logs, and CVE data can demonstrate detection and monitoring procedures",
            confidence="high",
            suggested_features=[
                "new_vulnerability_detection_count",
                "configuration_change_risk_score",
                "cve_detection_lag_days"
            ],
            required_entities=["Vulnerability", "CVE", "Configuration"],
            required_schemas=["vulnerability_instances", "cve", "configuration_changes"],
            related_metrics=["exploitable_vulnerabilities_count", "avg_patch_lag_days"]
        ),
        ComplianceControl(
            control_id="CC7.2",
            control_name="The Entity Monitors System Components and the Operation of Those Components",
            description="The entity monitors system components and the operation of those components to evaluate their performance in meeting the entity's objectives",
            framework="SOC2",
            category="System Operations",
            data_support="System monitoring logs, performance metrics, and operational data can demonstrate system monitoring",
            confidence="high",
            suggested_features=[
                "system_availability_rate",
                "performance_anomaly_count",
                "monitoring_coverage_rate"
            ],
            required_entities=["System", "Component"],
            required_schemas=["system_monitoring", "performance_metrics"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="CC7.3",
            control_name="The Entity Evaluates Security Events to Determine Whether They Could or Have Resulted in a Failure of the Entity's Objectives",
            description="The entity evaluates security events to determine whether they could or have resulted in a failure of the entity's objectives and takes action to prevent or address such failures",
            framework="SOC2",
            category="System Operations",
            data_support="Security event logs, incident reports, and threat intelligence data can demonstrate security event evaluation",
            confidence="high",
            suggested_features=[
                "security_incident_count",
                "threat_detection_rate",
                "incident_response_time_hours"
            ],
            required_entities=["SecurityEvent", "Incident"],
            required_schemas=["security_events", "incidents"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="CC7.4",
            control_name="The Entity Responds to Identified Security Incidents",
            description="The entity responds to identified security incidents by executing a defined incident-response program to understand, contain, remediate, and communicate security incidents",
            framework="SOC2",
            category="System Operations",
            data_support="Incident response logs, remediation records, and security event timelines can demonstrate incident response",
            confidence="high",
            suggested_features=[
                "incident_response_time_avg_hours",
                "incident_containment_rate",
                "remediation_completion_rate"
            ],
            required_entities=["Incident", "SecurityEvent"],
            required_schemas=["incidents", "incident_response"],
            related_metrics=["avg_remediation_time"]
        ),
        
        # CC8: Change Management
        ComplianceControl(
            control_id="CC8.1",
            control_name="The Entity Authorizes, Designs, Develops, Configures, Documents, Tests, Approves, and Implements Changes to Infrastructure, Data, Software, and Procedures",
            description="The entity authorizes, designs, develops, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures to meet its objectives",
            framework="SOC2",
            category="Change Management",
            data_support="Change management records, approval workflows, and deployment logs can demonstrate change management processes",
            confidence="high",
            suggested_features=[
                "change_approval_rate",
                "unauthorized_change_count",
                "change_rollback_rate"
            ],
            required_entities=["Change", "Deployment"],
            required_schemas=["change_management", "deployments"],
            related_metrics=[]
        ),
        
        # PCI-DSS Controls
        ComplianceControl(
            control_id="PCI-REQ-6",
            control_name="Develop and Maintain Secure Systems and Applications",
            description="Develop and maintain secure systems and applications by installing applicable vendor-supplied security patches within one month of release",
            framework="PCI-DSS",
            category="Vulnerability Management",
            data_support="Patch deployment records, vulnerability scan data, and software inventory can demonstrate patch management compliance",
            confidence="high",
            suggested_features=[
                "patch_deployment_lag_days",
                "critical_patch_compliance_rate",
                "unpatched_vulnerability_count"
            ],
            required_entities=["Patch", "Software", "Vulnerability"],
            required_schemas=["software_instances", "patch_deployments", "vulnerability_instances"],
            related_metrics=["avg_patch_lag_days", "sla_breached_count"]
        ),
        ComplianceControl(
            control_id="PCI-REQ-11",
            control_name="Regularly Test Security Systems and Processes",
            description="Regularly test security systems and processes, including vulnerability scanning and penetration testing",
            framework="PCI-DSS",
            category="Security Testing",
            data_support="Vulnerability scan results, penetration test reports, and security testing schedules can demonstrate regular security testing",
            confidence="high",
            suggested_features=[
                "vulnerability_scan_frequency",
                "penetration_test_coverage_rate",
                "security_test_compliance_rate"
            ],
            required_entities=["Vulnerability", "SecurityTest"],
            required_schemas=["vulnerability_instances", "security_tests"],
            related_metrics=["exploitable_vulnerabilities_count"]
        ),
        
        # HIPAA Controls
        ComplianceControl(
            control_id="HIPAA-164.308",
            control_name="Administrative Safeguards - Security Management Process",
            description="Implement policies and procedures to prevent, detect, contain, and correct security violations",
            framework="HIPAA",
            category="Security Management",
            data_support="Security incident logs, policy compliance data, and violation records can demonstrate security management processes",
            confidence="high",
            suggested_features=[
                "security_violation_count",
                "policy_compliance_rate",
                "incident_detection_time_avg_hours"
            ],
            required_entities=["SecurityEvent", "Policy"],
            required_schemas=["security_events", "policy_compliance"],
            related_metrics=["avg_remediation_time"]
        ),
        ComplianceControl(
            control_id="HIPAA-164.312",
            control_name="Technical Safeguards - Access Control",
            description="Implement technical policies and procedures for electronic information systems that maintain ePHI to allow access only to those persons or software programs that have been granted access rights",
            framework="HIPAA",
            category="Access Control",
            data_support="Access logs, user permissions, and authentication records can demonstrate access control implementation",
            confidence="high",
            suggested_features=[
                "unauthorized_access_attempts_count",
                "access_review_compliance_rate",
                "privileged_access_count"
            ],
            required_entities=["User", "Access"],
            required_schemas=["access_logs", "user_permissions"],
            related_metrics=[]
        ),
    ],
    control_categories={
        "Logical and Physical Access Controls": ["CC6.1", "CC6.2", "CC6.3", "CC6.6", "CC6.7", "HIPAA-164.312"],
        "System Operations": ["CC7.1", "CC7.2", "CC7.3", "CC7.4"],
        "Change Management": ["CC8.1"],
        "Vulnerability Management": ["PCI-REQ-6"],
        "Security Testing": ["PCI-REQ-11"],
        "Security Management": ["HIPAA-164.308"]
    }
)


# HR Compliance Domain Controls (GDPR, HIPAA, SOC2)
HR_COMPLIANCE_CONTROLS = ComplianceControlSet(
    domain_name="hr_compliance",
    framework="GDPR",
    controls=[
        # Training and Learning Compliance
        ComplianceControl(
            control_id="HR-TRAIN-001",
            control_name="Mandatory Training Completion",
            description="All employees must complete mandatory training courses within specified deadlines to maintain compliance with regulatory requirements",
            framework="GDPR",
            category="Training Compliance",
            data_support="Training completion records, enrollment data, and deadline tracking can demonstrate training compliance",
            confidence="high",
            suggested_features=[
                "training_completion_rate",
                "overdue_training_count",
                "compliance_gap_count"
            ],
            required_entities=["Employee", "Training", "Course"],
            required_schemas=["training_instances", "employee", "course"],
            related_metrics=["training_completion_rate", "registrations_at_risk", "employees_at_risk"]
        ),
        ComplianceControl(
            control_id="HR-TRAIN-002",
            control_name="Training Deadline Compliance",
            description="Training courses must be completed by their assigned due dates to ensure timely compliance with regulatory requirements",
            framework="GDPR",
            category="Training Compliance",
            data_support="Training deadline data, completion timestamps, and overdue tracking can demonstrate deadline compliance",
            confidence="high",
            suggested_features=[
                "deadline_compliance_rate",
                "overdue_training_count",
                "avg_days_past_deadline"
            ],
            required_entities=["Employee", "Training"],
            required_schemas=["training_instances", "employee"],
            related_metrics=["registrations_at_risk", "employees_at_risk", "overdue_courses_by_department"]
        ),
        ComplianceControl(
            control_id="HR-TRAIN-003",
            control_name="Training Progress Monitoring",
            description="Employee training progress must be monitored to identify at-risk registrations and provide timely interventions",
            framework="GDPR",
            category="Training Compliance",
            data_support="Learning progress data, enrollment records, and completion tracking can demonstrate progress monitoring",
            confidence="high",
            suggested_features=[
                "avg_learning_progress",
                "at_risk_registration_count",
                "learning_progress_variance"
            ],
            required_entities=["Employee", "Course"],
            required_schemas=["learning_instances", "course"],
            related_metrics=["avg_learning_progress", "los_at_risk_per_employee"]
        ),
        
        # Certification Compliance
        ComplianceControl(
            control_id="HR-CERT-001",
            control_name="Certification Expiry Management",
            description="Employee certifications must be tracked and renewed before expiration to maintain compliance and competency",
            framework="GDPR",
            category="Certification Compliance",
            data_support="Certification records, expiry dates, and renewal tracking can demonstrate certification management",
            confidence="high",
            suggested_features=[
                "expiring_certifications_count",
                "expired_certification_count",
                "certification_renewal_rate"
            ],
            required_entities=["Employee", "Certification"],
            required_schemas=["certifications", "employee"],
            related_metrics=["expiring_certifications_count"]
        ),
        ComplianceControl(
            control_id="HR-CERT-002",
            control_name="Required Certification Compliance",
            description="Employees in specific roles must maintain required certifications to perform their job functions",
            framework="GDPR",
            category="Certification Compliance",
            data_support="Role requirements, certification assignments, and compliance status can demonstrate required certification compliance",
            confidence="high",
            suggested_features=[
                "missing_required_certification_count",
                "certification_compliance_rate",
                "role_certification_gap_count"
            ],
            required_entities=["Employee", "Role", "Certification"],
            required_schemas=["employee", "certifications", "role_requirements"],
            related_metrics=["compliance_gap_count"]
        ),
        
        # Data Privacy and Access Controls (GDPR)
        ComplianceControl(
            control_id="GDPR-ART-5",
            control_name="Principles Relating to Processing of Personal Data",
            description="Personal data must be processed lawfully, fairly, and transparently, and collected for specified, explicit, and legitimate purposes",
            framework="GDPR",
            category="Data Privacy",
            data_support="Data processing logs, consent records, and purpose limitation documentation can demonstrate GDPR compliance",
            confidence="medium",
            suggested_features=[
                "data_processing_compliance_rate",
                "consent_management_rate",
                "purpose_limitation_violations_count"
            ],
            required_entities=["DataProcessing", "Consent"],
            required_schemas=["data_processing_logs", "consent_records"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="GDPR-ART-15",
            control_name="Right of Access by the Data Subject",
            description="Data subjects have the right to obtain confirmation as to whether personal data concerning them is being processed and access to that data",
            framework="GDPR",
            category="Data Subject Rights",
            data_support="Data access request logs, response times, and fulfillment records can demonstrate data subject rights compliance",
            confidence="high",
            suggested_features=[
                "data_access_request_count",
                "access_request_response_time_avg_days",
                "access_request_fulfillment_rate"
            ],
            required_entities=["DataSubject", "AccessRequest"],
            required_schemas=["data_access_requests"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="GDPR-ART-17",
            control_name="Right to Erasure ('Right to be Forgotten')",
            description="Data subjects have the right to obtain the erasure of personal data concerning them without undue delay",
            framework="GDPR",
            category="Data Subject Rights",
            data_support="Erasure request logs, processing times, and completion records can demonstrate erasure right compliance",
            confidence="high",
            suggested_features=[
                "erasure_request_count",
                "erasure_processing_time_avg_days",
                "erasure_completion_rate"
            ],
            required_entities=["DataSubject", "ErasureRequest"],
            required_schemas=["erasure_requests"],
            related_metrics=[]
        ),
        
        # HIPAA HR Controls
        ComplianceControl(
            control_id="HIPAA-HR-001",
            control_name="Workforce Security Management",
            description="Implement policies and procedures to ensure all members of the workforce have appropriate access to ePHI and to prevent workforce members who do not have access from obtaining access",
            framework="HIPAA",
            category="Workforce Security",
            data_support="Access authorization records, training completion data, and access review logs can demonstrate workforce security management",
            confidence="high",
            suggested_features=[
                "unauthorized_access_count",
                "access_review_compliance_rate",
                "workforce_training_completion_rate"
            ],
            required_entities=["Employee", "Access"],
            required_schemas=["employee", "access_logs", "training_instances"],
            related_metrics=["training_completion_rate"]
        ),
        ComplianceControl(
            control_id="HIPAA-HR-002",
            control_name="Workforce Clearance Procedures",
            description="Implement procedures to determine that the access of a workforce member to ePHI is appropriate",
            framework="HIPAA",
            category="Workforce Security",
            data_support="Clearance records, background check data, and access authorization logs can demonstrate clearance procedures",
            confidence="medium",
            suggested_features=[
                "clearance_completion_rate",
                "background_check_compliance_rate",
                "unauthorized_access_attempts_count"
            ],
            required_entities=["Employee", "Clearance"],
            required_schemas=["employee", "clearance_records"],
            related_metrics=[]
        ),
        
        # SOC2 HR Controls
        ComplianceControl(
            control_id="SOC2-HR-001",
            control_name="Personnel Security",
            description="The entity authorizes and supervises personnel and service providers who have access to confidential information or resources",
            framework="SOC2",
            category="Personnel Security",
            data_support="Personnel authorization records, supervision logs, and access monitoring data can demonstrate personnel security",
            confidence="high",
            suggested_features=[
                "unauthorized_personnel_access_count",
                "supervision_compliance_rate",
                "personnel_authorization_rate"
            ],
            required_entities=["Employee", "Personnel"],
            required_schemas=["employee", "personnel_records"],
            related_metrics=[]
        ),
        ComplianceControl(
            control_id="SOC2-HR-002",
            control_name="Training and Awareness",
            description="The entity provides training and awareness programs to personnel to support security objectives",
            framework="SOC2",
            category="Training and Awareness",
            data_support="Training completion records, awareness program participation, and competency assessments can demonstrate training and awareness",
            confidence="high",
            suggested_features=[
                "training_completion_rate",
                "awareness_program_participation_rate",
                "competency_assessment_pass_rate"
            ],
            required_entities=["Employee", "Training"],
            required_schemas=["training_instances", "employee"],
            related_metrics=["training_completion_rate", "historic_compliance_rate"]
        ),
        
        # Compliance Gap Management
        ComplianceControl(
            control_id="HR-GAP-001",
            control_name="Compliance Gap Identification",
            description="Organizations must identify and track employees who are missing required training, certifications, or other compliance requirements",
            framework="GDPR",
            category="Compliance Management",
            data_support="Compliance status records, requirement assignments, and gap analysis data can demonstrate gap identification",
            confidence="high",
            suggested_features=[
                "compliance_gap_count",
                "gap_severity_distribution",
                "gap_remediation_rate"
            ],
            required_entities=["Employee", "ComplianceRequirement"],
            required_schemas=["employee", "training_instances", "certifications"],
            related_metrics=["compliance_gap_count", "overdue_courses_by_department"]
        ),
        ComplianceControl(
            control_id="HR-GAP-002",
            control_name="Compliance Risk Assessment",
            description="Organizations must assess compliance risk based on factors such as overdue training, expiring certifications, and completion rates",
            framework="GDPR",
            category="Compliance Management",
            data_support="Risk assessment data, compliance metrics, and predictive factors can demonstrate risk assessment processes",
            confidence="high",
            suggested_features=[
                "compliance_risk_score",
                "at_risk_employee_count",
                "risk_factor_distribution"
            ],
            required_entities=["Employee", "Risk"],
            required_schemas=["training_instances", "employee"],
            related_metrics=["primary_risk_factors", "predictive_factors_completion"]
        ),
    ],
    control_categories={
        "Training Compliance": ["HR-TRAIN-001", "HR-TRAIN-002", "HR-TRAIN-003"],
        "Certification Compliance": ["HR-CERT-001", "HR-CERT-002"],
        "Data Privacy": ["GDPR-ART-5"],
        "Data Subject Rights": ["GDPR-ART-15", "GDPR-ART-17"],
        "Workforce Security": ["HIPAA-HR-001", "HIPAA-HR-002"],
        "Personnel Security": ["SOC2-HR-001"],
        "Training and Awareness": ["SOC2-HR-002"],
        "Compliance Management": ["HR-GAP-001", "HR-GAP-002"]
    }
)


# Control set registry
COMPLIANCE_CONTROL_SETS: Dict[str, ComplianceControlSet] = {
    "cybersecurity": CYBERSECURITY_CONTROLS,
    "hr_compliance": HR_COMPLIANCE_CONTROLS,
}


def get_compliance_control_set(domain_name: str) -> ComplianceControlSet:
    """Get compliance control set by domain name"""
    if domain_name not in COMPLIANCE_CONTROL_SETS:
        raise ValueError(
            f"Unknown domain: {domain_name}. "
            f"Available domains: {list(COMPLIANCE_CONTROL_SETS.keys())}"
        )
    return COMPLIANCE_CONTROL_SETS[domain_name]


def find_controls_by_keyword(keyword: str, domain_name: Optional[str] = None) -> List[ComplianceControl]:
    """Find compliance controls that match a keyword
    
    Args:
        keyword: Keyword to search for
        domain_name: Optional domain name to search within. If None, searches all domains.
    
    Returns:
        List of matching ComplianceControl objects
    """
    if domain_name:
        control_set = get_compliance_control_set(domain_name)
        return control_set.find_controls_by_keyword(keyword)
    else:
        # Search across all domains
        all_matches = []
        for control_set in COMPLIANCE_CONTROL_SETS.values():
            matches = control_set.find_controls_by_keyword(keyword)
            all_matches.extend(matches)
        return all_matches


def get_controls_for_framework(framework: str) -> List[ComplianceControl]:
    """Get all controls for a specific compliance framework across all domains
    
    Args:
        framework: Framework name (e.g., 'SOC2', 'GDPR', 'HIPAA', 'PCI-DSS')
    
    Returns:
        List of ComplianceControl objects for the framework
    """
    all_controls = []
    for control_set in COMPLIANCE_CONTROL_SETS.values():
        framework_controls = [c for c in control_set.controls if c.framework.upper() == framework.upper()]
        all_controls.extend(framework_controls)
    return all_controls

