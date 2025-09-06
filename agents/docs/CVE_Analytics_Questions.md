
# 📊 CVE Analytics Sample Questions

This document provides a categorized set of sample natural language questions for CVE analysis, inspired by the CVE Analytics dashboard structure. These questions are useful for SQL Agents, Insight Agents, and Dashboard visualizations.

---

## 🔍 Time Series Trend Questions

| Question | Visualization Type | Intent |
|----------|--------------------|--------|
| How has the total number of detected CVEs changed month-over-month? | Line Chart | Trend Analysis |
| What is the trend of newly remediated CVEs over the last 6 quarters? | Line Chart / Table | Remediation Velocity |
| Show weekly new CVEs broken down by severity (Critical, High, Medium, Low). | Stacked Bar Chart | Threat Volume Monitoring |
| How many new vulnerabilities were detected each week for Google Chrome in the past 3 months? | Line Chart + Product Filter | Product-focused CVE Influx |
| Compare quarterly fixed vs. open CVEs for the top 5 asset categories. | Side-by-side Bar Chart | Remediation Comparison |

---

## 🧱 Bucketed Distribution Questions

| Question | Visualization Type | Bucket Dimension |
|----------|--------------------|------------------|
| How many CVEs fall into each severity level? | Vertical Bar Chart | Severity |
| Show CVE distribution by threat level and device group (e.g., NY servers vs. DMZ servers). | Grouped Bar Chart | Group × Threat |
| What is the age breakdown of unresolved CVEs (0–30, 31–60, etc.)? | Horizontal Bar Chart | CVE Age |
| How do CVEs break down across software vendors like Microsoft, Adobe, and Google? | Stacked Bar | Vendor |
| Compare Balbix score buckets for open CVEs (e.g., 0–20, 21–40, etc.). | Side-by-side Bar | Balbix Score Bucket |

---

## 💻 Top N and Ranking Questions

| Question | Visualization Type | Focus |
|----------|--------------------|-------|
| Which 5 software products have the most open CVEs today? | Horizontal Bar | Top Vulnerable Software |
| What are the top 10 assets with the highest number of unresolved critical vulnerabilities? | Horizontal Bar | Asset Risk |
| Rank the top 10 CVEs by GTM risk score. | Table | Risk Prioritization |
| Which operating systems have the highest volume of unpatched CVEs? | Table or Column Chart | OS Risk Mapping |
| Show top 5 applications that introduced the most new vulnerabilities last month. | Column Chart | Software Ingress Analysis |

---

## 📈 Remediation, Patching, and Coverage

| Question | Visualization Type | Risk Ops |
|----------|--------------------|----------|
| What percentage of CVEs have been fixed in the last 90 days? | KPI + Donut | Patch Coverage |
| Which asset types have the lowest patch coverage? | Bar Chart | Patching Gaps |
| What is the average time-to-remediate for critical CVEs? | Line Chart or Table | TTR Monitoring |
| Show devices where patches are available but not applied for >60 days. | Table | Patch Latency |
| Compare the number of fixed vs. unfixed CVEs for software with known exploits. | Stacked Bar Chart | Exploit-Aware Remediation |

---

## ⚠️ Threat & Severity Management

| Question | Visualization Type | Threat Prioritization |
|----------|--------------------|------------------------|
| How many critical CVEs are older than 90 days and still open? | KPI or Table | Aging Risk |
| Compare high-severity CVEs with threat level “Confirmed Exploit” across business units. | Grouped Bar Chart | Business Exposure |
| What is the distribution of CVEs with CVSS >9 by region (e.g., North America, APAC)? | Heatmap | Geo-Risk Mapping |
| Which asset groups have CVEs with both High Balbix score and Threat Level = “High”? | Table | Compound Risk Filters |

---

## 📦 Software Exposure Over Time

| Question | Visualization Type | Software Risk |
|----------|--------------------|----------------|
| Track the number of newly vulnerable software installations per month. | Line Chart | Software Ingress |
| How has the number of patched software instances changed quarter-over-quarter? | Line Chart | Patch Adoption |
| Show software categorized by severity of CVEs affecting them. | Stacked Bar Chart | Software Risk Profile |
| Which software families have the largest number of critical CVEs unresolved? | Table | Vendor Risk Exposure |

---

## 🧠 Advanced or Derived Questions

| Question | Visualization Type | Advanced Insights |
|----------|--------------------|-------------------|
| Are CVEs with confirmed exploits remediated faster than those without? | Side-by-side Bar Chart | Behavior Analysis |
| What % of CVEs have been resolved within SLA timelines? | KPI + Line Chart | SLA Monitoring |
| Are critical CVEs clustering in specific business units or software types? | Clustered Heatmap | Risk Clustering |
| Which products are regressing—i.e., patched last quarter, but reintroduced vulnerabilities this month? | Table or Flag List | Risk Regression |
| What is the CVE backlog trend for assets in the cloud vs. on-prem? | Line Chart | Infra Comparison |
