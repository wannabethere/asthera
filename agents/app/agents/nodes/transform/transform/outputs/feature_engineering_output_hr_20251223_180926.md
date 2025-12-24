# Feature Engineering Pipeline Output (HR Compliance)

**Generated at:** 2025-12-23 18:09:26
**Domain:** HR Compliance
**Project ID:** cornerstone_learning

## Recommended Features (0 total)


## Impact Features (6 total)

### 1. training_completion_rate_impact
**Natural Language Question:** What is the training completion rate for GDPR compliance across departments?
**Description:** Measures the percentage of employees who have completed GDPR training within the required timeframe.
**Impact Type:** operational
**Feature Type:** float
**Calculation Logic:** (Number of employees who completed training / Total number of employees required to complete training) * 100
**Related Features:** 
**Knowledge Based Reasoning:** Completion rates are critical for assessing compliance with GDPR training requirements.

### 2. certification_expiry_impact
**Natural Language Question:** What is the number of certifications that are nearing expiry across departments?
**Description:** Counts the number of certifications that will expire within the next 30 days.
**Impact Type:** operational
**Feature Type:** integer
**Calculation Logic:** Count of certifications with expiry dates within the next 30 days
**Related Features:** 
**Knowledge Based Reasoning:** Tracking certification expiry is essential for maintaining compliance and ensuring employees are up-to-date.

### 3. compliance_gap_impact
**Natural Language Question:** What is the number of compliance gaps identified by department for GDPR training?
**Description:** Identifies the number of employees who have not completed required GDPR training by department.
**Impact Type:** operational
**Feature Type:** integer
**Calculation Logic:** Total number of employees required to complete training - Number of employees who completed training
**Related Features:** training_completion_rate_impact
**Knowledge Based Reasoning:** Identifying compliance gaps helps in understanding areas that need immediate attention to meet GDPR requirements.

### 4. departmental_training_variance_impact
**Natural Language Question:** What is the variance in training completion rates across different departments?
**Description:** Measures the difference in training completion rates between the highest and lowest performing departments.
**Impact Type:** operational
**Feature Type:** float
**Calculation Logic:** Max(training completion rates by department) - Min(training completion rates by department)
**Related Features:** training_completion_rate_impact
**Knowledge Based Reasoning:** Understanding variance helps identify departments that may require additional support or resources.

### 5. critical_deadline_impact
**Natural Language Question:** How many employees have training deadlines classified as critical (7 days)?
**Description:** Counts the number of employees whose training completion deadlines are within the next 7 days.
**Impact Type:** operational
**Feature Type:** integer
**Calculation Logic:** Count of employees with training deadlines within the next 7 days
**Related Features:** 
**Knowledge Based Reasoning:** Identifying critical deadlines is crucial for prioritizing training efforts and ensuring compliance.

### 6. high_deadline_impact
**Natural Language Question:** How many employees have training deadlines classified as high (30 days)?
**Description:** Counts the number of employees whose training completion deadlines are within the next 30 days but not critical.
**Impact Type:** operational
**Feature Type:** integer
**Calculation Logic:** Count of employees with training deadlines between 8 and 30 days
**Related Features:** 
**Knowledge Based Reasoning:** Tracking high deadlines helps in planning and resource allocation for training compliance.


## Likelihood Features (10 total)

### 1. historical_failure_rate
**Natural Language Question:** What is the historical failure rate for training compliance in GDPR across departments?
**Description:** Rate of past failures in training completion and compliance audits related to GDPR.
**Likelihood Type:** historical_failure
**Feature Type:** float
**Calculation Logic:** Number of past failures divided by total training sessions conducted over a defined period.
**Related Features:** 
**Knowledge Based Reasoning:** Historical failures indicate potential future failures, as patterns often repeat.

### 2. control_drift_frequency
**Natural Language Question:** How frequently do training materials and compliance requirements drift from the established baseline?
**Description:** Frequency of changes in training content or compliance requirements that deviate from the baseline.
**Likelihood Type:** control_drift
**Feature Type:** float
**Calculation Logic:** Count of configuration changes in training materials over a specified time frame.
**Related Features:** 
**Knowledge Based Reasoning:** Frequent changes can lead to confusion and non-compliance, increasing the likelihood of control failure.

### 3. evidence_quality_score
**Natural Language Question:** What is the quality score of evidence for training completion and compliance?
**Description:** Score assessing the completeness and currency of evidence related to training completion.
**Likelihood Type:** evidence_quality
**Feature Type:** float
**Calculation Logic:** Weighted score based on completeness, accuracy, and timeliness of evidence collected.
**Related Features:** 
**Knowledge Based Reasoning:** Poor quality evidence can mask compliance issues, leading to undetected failures.

### 4. process_volatility
**Natural Language Question:** What is the volatility of the training process for GDPR compliance?
**Description:** Measure of how often the training process changes, affecting stability.
**Likelihood Type:** process_volatility
**Feature Type:** float
**Calculation Logic:** Count of process changes (e.g., training delivery methods, content updates) over a defined period.
**Related Features:** 
**Knowledge Based Reasoning:** High volatility can disrupt training effectiveness, increasing the risk of non-compliance.

### 5. human_dependency_score
**Natural Language Question:** What is the level of human dependency in the training process for GDPR compliance?
**Description:** Ratio of manual processes to automated processes in training delivery and compliance tracking.
**Likelihood Type:** human_dependency
**Feature Type:** float
**Calculation Logic:** Percentage of training processes that are manual versus automated.
**Related Features:** 
**Knowledge Based Reasoning:** Higher human dependency increases the risk of errors and omissions, leading to potential control failures.

### 6. operational_load_factor
**Natural Language Question:** What is the operational load factor for training compliance across departments?
**Description:** Measure of the scale of training operations, including the number of employees and training sessions.
**Likelihood Type:** operational_load
**Feature Type:** float
**Calculation Logic:** Total number of training sessions divided by the number of employees requiring training.
**Related Features:** 
**Knowledge Based Reasoning:** Higher operational load can strain resources, leading to oversight and increased likelihood of control failure.

### 7. control_maturity_level
**Natural Language Question:** What is the maturity level of the training compliance controls in place for GDPR?
**Description:** Assessment of the maturity of controls related to training compliance on a scale of 1 to 5.
**Likelihood Type:** control_maturity
**Feature Type:** float
**Calculation Logic:** CMM-style assessment based on defined criteria for control effectiveness.
**Related Features:** 
**Knowledge Based Reasoning:** Higher maturity levels indicate stronger controls, reducing the likelihood of failure.

### 8. raw_likelihood
**Natural Language Question:** What is the overall raw likelihood score for training compliance in GDPR?
**Description:** Overall raw likelihood score without considering controls.
**Likelihood Type:** overall
**Feature Type:** float
**Calculation Logic:** Weighted combination of all likelihood factors.
**Related Features:** historical_failure_rate, control_drift_frequency, evidence_quality_score, process_volatility, human_dependency_score, operational_load_factor, control_maturity_level
**Knowledge Based Reasoning:** Combining multiple factors provides a comprehensive view of likelihood.

### 9. likelihood_active
**Natural Language Question:** What is the active likelihood (with controls) for training compliance in GDPR?
**Description:** Active likelihood considering current controls in place.
**Likelihood Type:** overall
**Feature Type:** float
**Calculation Logic:** Raw likelihood adjusted for active controls.
**Related Features:** raw_likelihood
**Knowledge Based Reasoning:** Active controls can mitigate risks, thus adjusting the likelihood.

### 10. likelihood_inherent
**Natural Language Question:** What is the inherent likelihood (without controls) for training compliance in GDPR?
**Description:** Inherent likelihood without considering controls.
**Likelihood Type:** overall
**Feature Type:** float
**Calculation Logic:** Base likelihood without considering controls.
**Related Features:** raw_likelihood
**Knowledge Based Reasoning:** Inherent likelihood provides a baseline for understanding risk without mitigation.


## Risk Features (5 total)

### 1. base_risk
**Natural Language Question:** What is the base risk score for GDPR training compliance based on likelihood and impact?
**Description:** Base risk score calculated from the likelihood of training compliance failures and the impact of those failures.
**Risk Type:** overall
**Feature Type:** float
**Risk Formula:** raw_likelihood * training_completion_rate_impact
**Calculation Logic:** Multiply raw likelihood by training completion rate impact to get the base risk score.
**Related Impact Features:** training_completion_rate_impact
**Related Likelihood Features:** raw_likelihood
**Knowledge Based Reasoning:** Base risk calculation follows standard risk assessment practices.

### 2. adjusted_risk
**Natural Language Question:** What is the adjusted risk score for GDPR training compliance considering contextual factors?
**Description:** Adjusted risk score that incorporates contextual factors affecting training compliance.
**Risk Type:** overall
**Feature Type:** float
**Risk Formula:** base_risk * temporal_multiplier * organizational_multiplier * sensitivity_multiplier * population_multiplier
**Calculation Logic:** Multiply base risk by contextual multipliers to adjust for various factors.
**Related Impact Features:** training_completion_rate_impact
**Related Likelihood Features:** raw_likelihood
**Knowledge Based Reasoning:** Adjusted risk considers temporal, organizational, sensitivity, and population factors.

### 3. critical_deadline_risk
**Natural Language Question:** What is the risk score for employees with critical training deadlines in GDPR compliance?
**Description:** Risk score specifically for employees with training deadlines classified as critical (7 days).
**Risk Type:** specific
**Feature Type:** float
**Risk Formula:** critical_deadline_impact * raw_likelihood
**Calculation Logic:** Multiply the number of critical deadlines by the overall raw likelihood to assess risk.
**Related Impact Features:** critical_deadline_impact
**Related Likelihood Features:** raw_likelihood
**Knowledge Based Reasoning:** Focuses on critical deadlines which pose immediate compliance risks.

### 4. high_deadline_risk
**Natural Language Question:** What is the risk score for employees with high training deadlines in GDPR compliance?
**Description:** Risk score for employees with training deadlines classified as high (30 days).
**Risk Type:** specific
**Feature Type:** float
**Risk Formula:** high_deadline_impact * raw_likelihood
**Calculation Logic:** Multiply the number of high deadlines by the overall raw likelihood to assess risk.
**Related Impact Features:** high_deadline_impact
**Related Likelihood Features:** raw_likelihood
**Knowledge Based Reasoning:** Addresses high deadlines which can lead to compliance gaps if not managed.

### 5. compliance_gap_risk
**Natural Language Question:** What is the risk score based on the number of compliance gaps identified for GDPR training?
**Description:** Risk score derived from the number of compliance gaps identified by department for GDPR training.
**Risk Type:** overall
**Feature Type:** float
**Risk Formula:** compliance_gap_impact * raw_likelihood
**Calculation Logic:** Multiply the number of compliance gaps by the overall raw likelihood to assess risk.
**Related Impact Features:** compliance_gap_impact
**Related Likelihood Features:** raw_likelihood
**Knowledge Based Reasoning:** Focuses on compliance gaps which indicate potential failures in training adherence.

