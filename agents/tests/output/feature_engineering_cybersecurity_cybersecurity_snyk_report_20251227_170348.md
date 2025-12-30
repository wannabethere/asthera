# Feature Engineering Pipeline Output

**Generated at:** 2025-12-27 17:03:48
**Domain:** cybersecurity
**Query:** 
            Create a report for Snyk that looks at the Critical and High vulnerabilities 
            for SOC2 compliance and provides risk, impact and likelihood metrics. I need to know SLAs, Repos, and Exploitability of the 
            vulnerabilities. Critical = 7 Days, High = 30 days since created and open and their risks.
            Yes use reachability. I want to understand the risk, impact and likelihood metrics for the report as well.
            Generate more than 20 features. 
            
**Success:** True

## Recommended Features (27 total)

### 1. critical_vulnerability_count

**Natural Language Question:** Count the number of vulnerabilities where severity is Critical and state is ACTIVE

**Type:** *: count

**Business Context:** *: This metric helps in understanding the current exposure to critical vulnerabilities that need immediate attention.

**Transformation Layer:** gold

**Required Schemas:** *: dev_assets

### 2. high_vulnerability_count

**Natural Language Question:** Count the number of vulnerabilities where severity is High and state is ACTIVE

**Type:** *: count

**Business Context:** *: This metric provides insight into the number of high-risk vulnerabilities that require remediation efforts.

**Transformation Layer:** gold

**Required Schemas:** *: dev_assets

### 3. critical_sla_breached_count

**Natural Language Question:** Count the number of critical vulnerabilities where (current_date - detected_time) > 7 days

**Type:** *: count

**Business Context:** *: This metric indicates how many critical vulnerabilities have exceeded the SLA for remediation, highlighting potential compliance issues.

**Transformation Layer:** gold

**Required Schemas:** *: dev_assets

### 4. high_sla_breached_count

**Natural Language Question:** Count the number of high vulnerabilities where (current_date - detected_time) > 30 days

**Type:** *: count

**Business Context:** *: This metric helps in assessing the effectiveness of the vulnerability management process for high-risk vulnerabilities.

**Transformation Layer:** gold

**Required Schemas:** *: dev_assets

### 5. critical_risk_vulnerability_count

**Natural Language Question:** Count the number of vulnerabilities classified as Critical risk

**Type:** *: count

**Business Context:** *: This metric provides insight into the number of vulnerabilities that pose a critical risk to the organization.

**Transformation Layer:** gold

**Required Schemas:** *: dev_assets

### 6. avg_remediation_time_days

**Natural Language Question:** Calculate the average number of days between detected_time and remediation_time for vulnerabilities where state is REMEDIATED

**Type:** *: metric

**Business Context:** *: This metric helps in evaluating the efficiency of the remediation process.

**Transformation Layer:** gold

**Required Schemas:** *: dev_assets

### 7. critical_vulnerability_impact_score

**Natural Language Question:** *: What is the impact score of critical vulnerabilities based on their classification and propagation?

**Type:** impact

**Calculation Logic:** *: Use the formula: `impact_score = calculate_asset_impact_class_score('Critical') *

**Business Context:** Risk feature for impact assessment

**SOC2 Compliance Reasoning:** Risk feature for impact assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 8. high_vulnerability_impact_score

**Natural Language Question:** *: What is the impact score of high vulnerabilities based on their classification and propagation?

**Type:** impact

**Calculation Logic:** *: Use the formula: `impact_score = calculate_asset_impact_class_score('High') *

**Business Context:** Risk feature for impact assessment

**SOC2 Compliance Reasoning:** Risk feature for impact assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 9. sla_breach_impact_score

**Natural Language Question:** *: How does the breach of SLAs for critical and high vulnerabilities affect overall impact?

**Type:** impact

**Calculation Logic:** *: Calculate the impact score by considering the number of SLA breaches: `impact_score = (critical_sla_breached_count * 10) + (high_sla_breached_count * 5)` to quantify the impact of SLA breaches.

**Business Context:** *: Monitoring SLA breaches is essential for maintaining compliance and ensuring timely remediation of vulnerabilities.

**SOC2 Compliance Reasoning:** *: Monitoring SLA breaches is essential for maintaining compliance and ensuring timely remediation of vulnerabilities.

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

=== likelihood features ===

**Required Schemas:** *: dev_assets

### 10. critical_vulnerability_breach_likelihood

**Natural Language Question:** *: What is the likelihood of a breach occurring due to critical vulnerabilities?

**Type:** impact

**Calculation Logic:** *: Use the formula: `likelihood = (critical_vulnerability_count *

**Business Context:** Risk feature for impact assessment

**SOC2 Compliance Reasoning:** Risk feature for impact assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 11. high_vulnerability_breach_likelihood

**Natural Language Question:** *: What is the likelihood of a breach occurring due to high vulnerabilities?

**Type:** impact

**Calculation Logic:** *: Calculate the likelihood using: `likelihood = (high_vulnerability_count *

**Business Context:** Risk feature for impact assessment

**SOC2 Compliance Reasoning:** Risk feature for impact assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 12. unpatched_vulnerability_likelihood

**Natural Language Question:** *: What is the likelihood of a breach due to unpatched vulnerabilities?

**Type:** impact

**Calculation Logic:** *: Use the formula: `likelihood = (critical_unpatched * 15 + high_unpatched * 10 + medium_unpatched * 5)` to quantify the likelihood based on unpatched vulnerabilities.

**Business Context:** *: Identifying the likelihood of breaches from unpatched vulnerabilities is essential for proactive risk management.

**SOC2 Compliance Reasoning:** *: Identifying the likelihood of breaches from unpatched vulnerabilities is essential for proactive risk management.

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

=== risk features ===

**Required Schemas:** *: dev_assets

### 13. critical_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for critical vulnerabilities based on their impact and likelihood?

**Type:** impact

**Calculation Logic:** *: Calculate the risk score using: `risk_score = (critical_vulnerability_impact_score *

**Business Context:** Risk feature for impact assessment

**SOC2 Compliance Reasoning:** Risk feature for impact assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 14. Transformation

**Natural Language Question:** Calculate Transformation

**Type:** impact

**Calculation Logic:** N/A

**Business Context:** Risk feature for impact assessment

**SOC2 Compliance Reasoning:** Risk feature for impact assessment

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

### 15. high_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for high vulnerabilities based on their impact and likelihood?

**Type:** impact

**Calculation Logic:** *: Use the formula: `risk_score = (high_vulnerability_impact_score *

**Business Context:** Risk feature for impact assessment

**SOC2 Compliance Reasoning:** Risk feature for impact assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 16. overall_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for all vulnerabilities considering both critical and high vulnerabilities?

**Type:** impact

**Calculation Logic:** *: Calculate the overall risk score using: `risk_score = (critical_vulnerability_risk_score + high_vulnerability_risk_score) / 2` to provide a comprehensive risk assessment.

**Business Context:** *: A comprehensive risk score helps organizations prioritize vulnerabilities and allocate resources effectively for remediation.

**SOC2 Compliance Reasoning:** *: A comprehensive risk score helps organizations prioritize vulnerabilities and allocate resources effectively for remediation.

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

**Required Schemas:** *: dev_assets

### 17. critical_vulnerability_breach_likelihood

**Natural Language Question:** *: What is the likelihood of a breach occurring due to critical vulnerabilities?

**Type:** likelihood

**Calculation Logic:** *: Use the formula: `likelihood = (critical_vulnerability_count *

**Business Context:** Risk feature for likelihood assessment

**SOC2 Compliance Reasoning:** Risk feature for likelihood assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 18. high_vulnerability_breach_likelihood

**Natural Language Question:** *: What is the likelihood of a breach occurring due to high vulnerabilities?

**Type:** likelihood

**Calculation Logic:** *: Calculate the likelihood using: `likelihood = (high_vulnerability_count *

**Business Context:** Risk feature for likelihood assessment

**SOC2 Compliance Reasoning:** Risk feature for likelihood assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 19. unpatched_vulnerability_likelihood

**Natural Language Question:** *: What is the likelihood of a breach due to unpatched vulnerabilities?

**Type:** likelihood

**Calculation Logic:** *: Use the formula: `likelihood = (critical_unpatched * 15 + high_unpatched * 10 + medium_unpatched * 5)` to quantify the likelihood based on unpatched vulnerabilities.

**Business Context:** *: Identifying the likelihood of breaches from unpatched vulnerabilities is essential for proactive risk management.

**SOC2 Compliance Reasoning:** *: Identifying the likelihood of breaches from unpatched vulnerabilities is essential for proactive risk management.

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

=== risk features ===

**Required Schemas:** *: dev_assets

### 20. critical_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for critical vulnerabilities based on their impact and likelihood?

**Type:** likelihood

**Calculation Logic:** *: Calculate the risk score using: `risk_score = (critical_vulnerability_impact_score *

**Business Context:** Risk feature for likelihood assessment

**SOC2 Compliance Reasoning:** Risk feature for likelihood assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 21. Transformation

**Natural Language Question:** Calculate Transformation

**Type:** likelihood

**Calculation Logic:** N/A

**Business Context:** Risk feature for likelihood assessment

**SOC2 Compliance Reasoning:** Risk feature for likelihood assessment

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

### 22. high_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for high vulnerabilities based on their impact and likelihood?

**Type:** likelihood

**Calculation Logic:** *: Use the formula: `risk_score = (high_vulnerability_impact_score *

**Business Context:** Risk feature for likelihood assessment

**SOC2 Compliance Reasoning:** Risk feature for likelihood assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 23. overall_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for all vulnerabilities considering both critical and high vulnerabilities?

**Type:** likelihood

**Calculation Logic:** *: Calculate the overall risk score using: `risk_score = (critical_vulnerability_risk_score + high_vulnerability_risk_score) / 2` to provide a comprehensive risk assessment.

**Business Context:** *: A comprehensive risk score helps organizations prioritize vulnerabilities and allocate resources effectively for remediation.

**SOC2 Compliance Reasoning:** *: A comprehensive risk score helps organizations prioritize vulnerabilities and allocate resources effectively for remediation.

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

**Required Schemas:** *: dev_assets

### 24. critical_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for critical vulnerabilities based on their impact and likelihood?

**Type:** risk

**Calculation Logic:** *: Calculate the risk score using: `risk_score = (critical_vulnerability_impact_score *

**Business Context:** Risk feature for risk assessment

**SOC2 Compliance Reasoning:** Risk feature for risk assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 25. Transformation

**Natural Language Question:** Calculate Transformation

**Type:** risk

**Calculation Logic:** N/A

**Business Context:** Risk feature for risk assessment

**SOC2 Compliance Reasoning:** Risk feature for risk assessment

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

### 26. high_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for high vulnerabilities based on their impact and likelihood?

**Type:** risk

**Calculation Logic:** *: Use the formula: `risk_score = (high_vulnerability_impact_score *

**Business Context:** Risk feature for risk assessment

**SOC2 Compliance Reasoning:** Risk feature for risk assessment

**Transformation Layer:** gold

**Time Series Type:** snapshot

### 27. overall_vulnerability_risk_score

**Natural Language Question:** *: What is the overall risk score for all vulnerabilities considering both critical and high vulnerabilities?

**Type:** risk

**Calculation Logic:** *: Calculate the overall risk score using: `risk_score = (critical_vulnerability_risk_score + high_vulnerability_risk_score) / 2` to provide a comprehensive risk assessment.

**Business Context:** *: A comprehensive risk score helps organizations prioritize vulnerabilities and allocate resources effectively for remediation.

**SOC2 Compliance Reasoning:** *: A comprehensive risk score helps organizations prioritize vulnerabilities and allocate resources effectively for remediation.

**Transformation Layer:** *: gold

**Time Series Type:** *: snapshot

**Required Schemas:** *: dev_assets


## Analytical Intent

```json
{
  "primary_goal": "primary_goal='Create a report for Snyk that looks at the Critical and High vulnerabilities for SOC2 compliance and provides risk, impact and likelihood metrics.' compliance_framework='SOC2' severity_l",
  "compliance_framework": "",
  "severity_levels": [],
  "time_constraints": null,
  "metrics_required": [],
  "aggregation_level": "",
  "time_series_requirements": false
}
```


## Relevant Schemas

- dev_assets


## Clarifying Questions

1. 1. **Question:** What specific time window should we consider for assessing the Critical and High vulnerabilities in relation to SOC2 compliance?
2. 2. **Question:** Which specific metrics do you want to include for assessing risk, impact, and likelihood related to the identified vulnerabilities?
3. 3. **Question:** Which specific assets or categories of assets should be included in the analysis of vulnerabilities for SOC2 compliance?
4. 4. **Question:** What aggregation methods and grouping criteria should be applied when compiling the report on vulnerabilities?
5. 5. **Question:** Are there any specific definitions or standards for the missing metrics that need to be established for this report?

