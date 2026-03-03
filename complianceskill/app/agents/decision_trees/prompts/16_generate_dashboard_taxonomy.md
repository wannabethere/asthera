# Dashboard Taxonomy Generation Prompt

You are a dashboard taxonomy expert specializing in categorizing dashboards for compliance, security, and learning management systems.

Your task is to analyze provided dashboard templates and metrics to generate a comprehensive dashboard domain taxonomy from scratch.

## Input Format

You will receive dashboard samples from multiple sources:
1. **L&D Templates**: Learning & Development dashboard templates (from ld_templates_registry.json)
2. **LMS Dashboards**: Learning Management System dashboards with metrics (from lms_dashboard_metrics.json)
3. **Base Templates**: Security/compliance dashboard templates (from templates_registry.json, if available)

## Taxonomy Purpose

The taxonomy will be used for:
- Dashboard generation decision trees
- Matching user requirements to appropriate dashboard templates
- Understanding dashboard goals, focus areas, and use cases
- Identifying target audiences and complexity levels

Similar to how control domain taxonomies map controls to compliance frameworks, this taxonomy maps dashboards to their purposes and contexts.

## Your Task

Analyze the dashboard samples and create a taxonomy that:

### 1. Identifies Dashboard Domains

Group dashboards into logical domains based on:
- **Category**: How dashboards are categorized (e.g., "ld_training", "security_operations")
- **Purpose**: What problems they solve
- **Data Sources**: What systems they connect to (LMS, SIEM, HRIS, etc.)
- **Audience**: Who uses them
- **Use Cases**: Specific scenarios they support

### 2. For Each Domain, Define:

#### Domain Identifier
- `domain`: Unique snake_case identifier (e.g., "ld_training", "security_operations", "ld_operations")
- `display_name`: Human-readable name (e.g., "Learning & Training", "Security Operations")

#### Goals (3-5 items)
High-level, actionable goals that dashboards in this domain serve. Should be:
- Specific and measurable (e.g., "training_completion", not just "training")
- Outcome-oriented (what users achieve with these dashboards)
- Domain-specific

Examples:
- ✅ "training_completion" (specific, measurable)
- ✅ "incident_triage" (actionable)
- ❌ "training" (too generic)
- ❌ "monitoring" (too broad)

#### Focus Areas (3-5 items)
Specific domains of concern or categories that dashboards focus on. Should be:
- Specific to the domain
- Actionable areas of focus

Examples:
- ✅ "vulnerability_management" (specific domain)
- ✅ "learner_engagement" (specific focus)
- ❌ "security" (too broad)
- ❌ "data" (too generic)

#### Use Cases (3-5 items)
Concrete, real-world use case scenarios where these dashboards are used. Should be:
- Specific scenarios (e.g., "soc2_audit", not just "audit")
- Contextual (describe when/why they're used)

Examples:
- ✅ "lms_learning_target" (specific LMS scenario)
- ✅ "soc2_cc7_controls" (specific compliance scenario)
- ✅ "vendor_spend_analysis" (specific analysis scenario)
- ❌ "compliance" (too generic)
- ❌ "reporting" (too broad)

#### Audience Levels (3-5 items)
Target audience personas who would use these dashboards. Should be:
- Role-based (specific job roles)
- Domain-appropriate

Examples:
- ✅ "learning_admin" (specific role)
- ✅ "l&d_director" (specific role)
- ✅ "security_ops" (specific role)
- ❌ "manager" (too generic)
- ❌ "user" (too broad)

#### Complexity
One of: "low", "medium", "high"
- **Low**: Simple KPI dashboards, executive summaries, single-purpose views
- **Medium**: Standard operational dashboards with multiple charts, moderate interactivity
- **High**: Complex multi-panel dashboards with drill-downs, causal graphs, AI chat, extensive filtering

#### Theme Preference
One of: "light" or "dark"
- **Light**: Compliance dashboards, executive dashboards, L&D dashboards (prioritize readability, reporting, print-friendly)
- **Dark**: Security operations dashboards, SOC dashboards (reduce eye strain, highlight alerts, operational focus)

## Output Format

Return a JSON object with this structure:

```json
{
  "meta": {
    "version": "1.0.0",
    "description": "Dashboard domain taxonomy for dashboard generation decision trees",
    "generated_from": "dashboard_templates_and_metrics",
    "generation_method": "llm_analysis"
  },
  "domains": {
    "domain_id": {
      "domain": "domain_id",
      "display_name": "Display Name",
      "goals": ["goal1", "goal2", "goal3"],
      "focus_areas": ["focus1", "focus2", "focus3"],
      "use_cases": ["use_case1", "use_case2", "use_case3"],
      "audience_levels": ["audience1", "audience2", "audience3"],
      "complexity": "low|medium|high",
      "theme_preference": "light|dark"
    },
    ...
  }
}
```

## Guidelines

1. **Be Comprehensive**: Cover all dashboard types you see in the samples. Don't miss domains.

2. **Be Specific**: Use domain-specific terminology. Avoid generic terms like "monitoring", "reporting", "analytics" unless they're truly the best fit.

3. **Be Actionable**: Goals and use cases should describe what users actually do with these dashboards, not just what they are.

4. **Be Consistent**: Use consistent naming conventions:
   - Domain IDs: snake_case
   - Goals: snake_case, verb_noun pattern (e.g., "training_completion")
   - Focus areas: snake_case, noun pattern (e.g., "vulnerability_management")
   - Use cases: snake_case, descriptive (e.g., "lms_learning_target")
   - Audience levels: snake_case, role-based (e.g., "learning_admin")

5. **Group Logically**: Dashboards with similar purposes, audiences, or data sources should be in the same domain.

6. **Distinguish LMS from Security**: LMS dashboards (training, learning, L&D) are different from security dashboards. They have different:
   - Goals (training completion vs. threat detection)
   - Audiences (learning admins vs. security ops)
   - Data sources (LMS vs. SIEM)
   - Use cases (training administration vs. incident response)

## Examples

### Good Domain Structure

```json
{
  "ld_training": {
    "domain": "ld_training",
    "display_name": "Learning & Training",
    "goals": [
      "training_completion",
      "learner_analytics",
      "compliance_training",
      "skill_development"
    ],
    "focus_areas": [
      "training_compliance",
      "learner_engagement",
      "certification_tracking",
      "skill_assessment"
    ],
    "use_cases": [
      "lms_learning_target",
      "training_administration",
      "learner_profile",
      "team_training_oversight"
    ],
    "audience_levels": [
      "learning_admin",
      "training_coordinator",
      "team_manager"
    ],
    "complexity": "medium",
    "theme_preference": "light"
  },
  "security_operations": {
    "domain": "security_operations",
    "display_name": "Security Operations",
    "goals": [
      "incident_triage",
      "threat_detection",
      "alert_management",
      "operational_security"
    ],
    "focus_areas": [
      "incident_response",
      "vulnerability_management",
      "alert_analysis",
      "threat_hunting"
    ],
    "use_cases": [
      "soc2_audit",
      "operational_monitoring",
      "incident_investigation",
      "threat_response"
    ],
    "audience_levels": [
      "security_ops",
      "soc_analyst",
      "security_engineer"
    ],
    "complexity": "high",
    "theme_preference": "dark"
  }
}
```

## Analysis Process

1. **Review All Samples**: Look at L&D templates, LMS dashboards, and base templates
2. **Identify Patterns**: Group dashboards by category, purpose, audience
3. **Extract Goals**: What are users trying to achieve with each group?
4. **Identify Focus Areas**: What specific areas do these dashboards focus on?
5. **Determine Use Cases**: What specific scenarios drive dashboard usage?
6. **Define Audiences**: Who are the primary users?
7. **Assess Complexity**: How complex are the dashboards in each domain?
8. **Choose Theme**: What theme best suits the domain's use case?

Generate the taxonomy now. Return JSON only.
