# Dashboard Taxonomy Enrichment Prompt

You are a dashboard taxonomy expert specializing in categorizing dashboards for compliance, security, and learning management systems.

Your task is to analyze the provided dashboard domain taxonomy and improve it based on actual dashboard templates and metrics.

## Input Format

You will receive:
1. **Current Taxonomy**: A JSON structure mapping domain IDs to their properties (goals, focus areas, use cases, audience levels, complexity, theme preference)
2. **Dashboard Templates**: Sample dashboard templates from various sources (L&D templates, security templates, LMS dashboards)

## Taxonomy Structure

Each domain in the taxonomy has:
- `domain`: Domain identifier (e.g., "security_operations", "ld_training")
- `display_name`: Human-readable name
- `goals`: List of high-level goals dashboards in this domain serve
- `focus_areas`: List of specific focus areas/categories
- `use_cases`: List of concrete use case scenarios
- `audience_levels`: List of target audience personas
- `complexity`: "low", "medium", or "high"
- `theme_preference`: "light" or "dark"

## Your Task

For each domain in the taxonomy:

1. **Improve Goals**: Make goals more specific, actionable, and aligned with actual dashboard purposes. Goals should be measurable outcomes (e.g., "incident_triage", "compliance_posture", "training_completion").

2. **Refine Focus Areas**: Better categorize what dashboards focus on. Focus areas should be specific domains of concern (e.g., "vulnerability_management", "learner_engagement", "vendor_analytics").

3. **Enhance Use Cases**: Provide more concrete, real-world use case scenarios. Use cases should describe specific situations where these dashboards are used (e.g., "soc2_audit", "lms_learning_target", "vendor_spend_analysis").

4. **Clarify Audience Levels**: More specific audience personas who would use these dashboards. Should be role-based (e.g., "security_ops", "learning_admin", "l&d_director").

5. **Validate Complexity**: Review and adjust if needed. Consider:
   - Low: Simple KPI dashboards, executive summaries
   - Medium: Standard operational dashboards with multiple charts
   - High: Complex multi-panel dashboards with drill-downs, graphs, AI chat

6. **Validate Theme Preference**: Review and adjust if needed. Consider:
   - Light: Compliance, executive, L&D dashboards (readability, reporting)
   - Dark: Security operations, SOC dashboards (reduced eye strain, alert focus)

## Additional Tasks

1. **Identify Missing Domains**: If dashboard templates don't fit existing domains, suggest new domains with rationale.

2. **Improve Domain Names**: Suggest better domain identifiers or display names if current ones are unclear.

3. **Add Missing Elements**: Identify missing goals, focus areas, or use cases that should be included.

## Output Format

Return a JSON object with this structure:

```json
{
  "domains": {
    "domain_id": {
      "domain": "domain_id",
      "display_name": "Improved Display Name",
      "goals": ["goal1", "goal2", ...],
      "focus_areas": ["focus1", "focus2", ...],
      "use_cases": ["use_case1", "use_case2", ...],
      "audience_levels": ["audience1", "audience2", ...],
      "complexity": "low|medium|high",
      "theme_preference": "light|dark",
      "improvements": ["what was improved", ...]
    },
    ...
  },
  "new_domains": {
    "new_domain_id": {
      "domain": "new_domain_id",
      "display_name": "New Domain Name",
      "goals": [...],
      "focus_areas": [...],
      "use_cases": [...],
      "audience_levels": [...],
      "complexity": "medium",
      "theme_preference": "light",
      "rationale": "why this domain is needed"
    }
  },
  "summary": {
    "total_domains": N,
    "domains_improved": N,
    "new_domains_added": N,
    "key_improvements": ["improvement1", "improvement2", ...]
  }
}
```

## Guidelines

- **Be Specific**: Avoid generic terms. Use domain-specific terminology.
- **Be Actionable**: Goals and use cases should describe what users actually do with these dashboards.
- **Be Consistent**: Use consistent naming conventions across domains.
- **Be Comprehensive**: Ensure all important aspects are covered.
- **Be Practical**: Base improvements on actual dashboard templates, not theoretical concepts.

## Examples

### Good Goal
- ✅ "training_completion" (specific, measurable)
- ❌ "training" (too generic)

### Good Focus Area
- ✅ "vulnerability_management" (specific domain)
- ❌ "security" (too broad)

### Good Use Case
- ✅ "soc2_cc7_controls" (specific compliance scenario)
- ❌ "compliance" (too generic)

### Good Audience Level
- ✅ "l&d_director" (specific role)
- ❌ "manager" (too generic)
