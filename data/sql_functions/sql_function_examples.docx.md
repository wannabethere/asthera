 

**SQL Function Library**

**Usage Examples & Reference Guide**

Cybersecurity Risk & Compliance Analytics Platform

Generated: Sun Feb 22 2026

 

| Metric | Value |
| ----- | ----- |
| Total Functions Covered | 27 detailed examples |
| Function Categories | 7 |
| Source Tables Referenced | metrics\_daily, risk\_impact\_metadata, breach\_method\_metadata, vulnerability\_tickets, daily\_auth\_events, daily\_security\_alerts, phishing\_simulation\_results, alert\_resolution |
| Input Format | JSONB arrays, scalar parameters, inline ARRAY\[\] |
| Output Format | Typed TABLE returns with rich metadata |

 

**Table of Contents**

**1\. Correlation & Anomaly Analysis**

    1.1  **find\_correlated\_metrics** *— Our revenue dropped sharply on Jan 15\. Which other metrics moved ...*

    1.2  **calculate\_lag\_correlation** *— Does p99 latency lead revenue drops — i.e., does latency spike a ...*

    1.3  **decompose\_impact\_by\_dimension** *— The Jan 15 revenue anomaly — which regions and product tiers cont...*

    1.4  **build\_anomaly\_explanation\_payload** *— Assemble a complete structured payload for the Jan 15 revenue ano...*

**2\. Impact Calculation**

    2.1  **calculate\_generic\_impact / build\_impact\_parameter** *— Score the business impact of a critical production database compr...*

    2.2  **calculate\_impact\_from\_json** *— Score the impact of a ransomware attack on a file server using a ...*

    2.3  **calculate\_cascading\_impact** *— A core authentication service is compromised. Estimate the blast ...*

    2.4  **classify\_impact\_level** *— Given a composite impact score of 83.7, what action tier does thi...*

    2.5  **calculate\_impact\_batch** *— Score and rank the business impact across five critical assets si...*

**3\. Likelihood Calculation**

    3.1  **calculate\_vulnerability\_likelihood** *— What is the likelihood of exploitation for a server with 3 critic...*

    3.2  **calculate\_time\_weighted\_likelihood** *— An unpatched CVE has been present for 45 days and the SLA deadlin...*

    3.3  **calculate\_asset\_likelihood** *— Compute a holistic breach likelihood score for asset 'db-prod-aut...*

    3.4  **calculate\_likelihood\_trend** *— Is this asset's breach likelihood getting better or worse over th...*

**4\. Moving Averages**

    4.1  **calculate\_sma** *— Smooth daily p99 latency over a 7-day rolling window and flag day...*

    4.2  **calculate\_bollinger\_bands** *— Apply Bollinger Bands to daily vulnerability scan counts to ident...*

    4.3  **calculate\_moving\_correlation** *— Is the historical relationship between CPU utilization and error ...*

**5\. Time Series Analysis**

    5.1  **calculate\_autocorrelation** *— Does daily login failure count show weekly periodicity? Test auto...*

    5.2  **test\_stationarity** *— Before feeding threat score history into a forecasting model, che...*

    5.3  **analyze\_distribution** *— Compare the distribution of remediation times between enterprise ...*

**6\. Trend Analysis**

    6.1  **calculate\_statistical\_trend** *— Is the number of open critical vulnerabilities trending up or dow...*

    6.2  **forecast\_linear** *— Based on the current remediation velocity, how many open critical...*

    6.3  **detect\_anomalies** *— Automatically flag days where login failure counts are statistica...*

    6.4  **detect\_seasonality** *— Does our weekly security alert volume show day-of-week seasonalit...*

**7\. A/B Testing & Operations**

    7.1  **calculate\_percent\_change\_comparison** *— Did deploying a new WAF ruleset (treatment) reduce error rates co...*

    7.2  **calculate\_bootstrap\_ci** *— What are the 95% confidence intervals around mean MTTR (mean time...*

    7.3  **calculate\_prepost\_comparison** *— After a security awareness training rollout, did phishing click r...*

    7.4  **calculate\_effect\_sizes** *— How large is the practical effect of our new endpoint detection t...*

 

# **1\. Correlation & Anomaly Analysis**

 

**Example 1.1 — find\_correlated\_metrics**

**❓  Natural Language Question**

*Our revenue dropped sharply on Jan 15\. Which other metrics moved with it during the same window?*

 

**📋  Description**

Scans all metrics in a 14-day lookback window ending at the anomaly date, computes Pearson correlation for every metric pair against revenue, and returns pairs ranked by correlation strength. Useful for quickly identifying correlated signals during an incident.

**🔢  Steps**

**1\.** Set the primary metric to 'revenue' and anomaly date to 2024-01-15.

**2\.** Pull a 14-day lookback window for all metrics from metrics\_daily.

**3\.** Compute Pearson correlation between revenue and each other metric.

**4\.** Filter out weak correlations below 0.60 and rank descending by absolute correlation.

 

**💾  SQL**

 

SELECT  
  metric\_pair,  
  correlated\_metric,  
  correlation,  
  direction,  
  data\_points,  
  window\_start,  
  window\_end  
FROM find\_correlated\_metrics(  
  'revenue',           \-- primary metric  
  '2024-01-15'::DATE,  \-- anomaly date  
  14,                  \-- lookback days  
  0.60                 \-- min correlation threshold  
)  
ORDER BY abs\_correlation DESC;  
 

**📊  Source Table: metrics\_daily**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| metric\_date | DATE | 2024-01-15 |
| metric\_name | TEXT | revenue |
| metric\_value | DECIMAL | 125000.00 |
| region | TEXT | us-east |
| product\_tier | TEXT | enterprise |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| metric\_pair | revenue ↔ p99\_latency\_ms |
| correlated\_metric | p99\_latency\_ms |
| correlation | \-0.8921 |
| direction | negative |
| data\_points | 14 |
| window\_start | 2024-01-01 |
| window\_end | 2024-01-15 |

 

 

**Example 1.2 — calculate\_lag\_correlation**

**❓  Natural Language Question**

*Does p99 latency lead revenue drops — i.e., does latency spike a day or two before revenue falls?*

 

**📋  Description**

Sweeps lag positions from \-5 to \+5 days between a metric pair. A negative lag means the secondary metric leads the primary (causal candidate). This reveals whether latency spikes are a leading indicator of revenue decline.

**🔢  Steps**

**1\.** Specify primary metric \= 'revenue', secondary \= 'p99\_latency\_ms'.

**2\.** Sweep lags from \-5 to \+5 around the anomaly date.

**3\.** Compute Pearson correlation at each lag position.

**4\.** Order by absolute correlation to find the strongest lag relationship.

 

**💾  SQL**

 

SELECT  
  lag\_periods,  
  lag\_direction,  
  correlation,  
  interpretation  
FROM calculate\_lag\_correlation(  
  'revenue',          \-- primary metric  
  'p99\_latency\_ms',   \-- other metric  
  '2024-01-15'::DATE, \-- anomaly date  
  14,                 \-- lookback window  
  5                   \-- max lag to sweep  
)  
ORDER BY abs\_correlation DESC  
LIMIT 5;  
 

**📊  Source Table: metrics\_daily**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| metric\_date | DATE | 2024-01-15 |
| metric\_name | TEXT | p99\_latency\_ms |
| metric\_value | DECIMAL | 4320.00 |
| region | TEXT | us-west |
| product\_tier | TEXT | enterprise |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| lag\_periods | \-2 |
| lag\_direction | p99\_latency\_ms leads revenue by 2 days |
| correlation | \-0.9112 |
| interpretation | Strong leading indicator: latency spikes 2 days before revenue drops |

 

 

**Example 1.3 — decompose\_impact\_by\_dimension**

**❓  Natural Language Question**

*The Jan 15 revenue anomaly — which regions and product tiers contributed most to the drop?*

 

**📋  Description**

Breaks the total anomaly impact into segment-level contributions by comparing actual values against a 7-day pre-anomaly baseline. Returns each segment's absolute delta and its percentage share of the total drop.

**🔢  Steps**

**1\.** Compute a 7-day baseline average per segment before the anomaly date.

**2\.** Compare each segment's anomaly-day actual against its baseline.

**3\.** Calculate absolute\_delta and contribution\_to\_total percentage.

**4\.** Rank segments by impact to identify the worst-hit segments.

 

**💾  SQL**

 

SELECT  
  dimension\_value,  
  baseline\_avg,  
  anomaly\_actual,  
  absolute\_delta,  
  pct\_delta,  
  segment\_weight,  
  contribution\_to\_total,  
  impact\_rank  
FROM decompose\_impact\_by\_dimension(  
  'revenue',           \-- metric name  
  '2024-01-15'::DATE,  \-- anomaly date  
  'region\_tier',       \-- dimension: region, product\_tier, region\_tier  
  7,                   \-- baseline days  
  1                    \-- comparison window width (days)  
)  
ORDER BY impact\_rank;  
 

**📊  Source Table: metrics\_daily**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| metric\_date | DATE | 2024-01-15 |
| metric\_name | TEXT | revenue |
| metric\_value | DECIMAL | 84000.00 |
| region | TEXT | us-east |
| product\_tier | TEXT | enterprise |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| dimension\_value | us-east / enterprise |
| baseline\_avg | 125000.00 |
| anomaly\_actual | 84000.00 |
| absolute\_delta | \-41000.00 |
| pct\_delta | \-32.8% |
| contribution\_to\_total | 58.3% |
| impact\_rank | 1 |

 

 

**Example 1.4 — build\_anomaly\_explanation\_payload**

**❓  Natural Language Question**

*Assemble a complete structured payload for the Jan 15 revenue anomaly to feed into an LLM explanation layer.*

 

**📋  Description**

Combines anomaly stats, correlated metrics, leading indicators (from lag analysis), and dimensional decomposition into a single JSONB payload. Designed to be passed directly to an LLM for narrative generation or to an orchestration layer.

**🔢  Steps**

**1\.** Compute anomaly statistics (z-score, percent deviation).

**2\.** Run find\_correlated\_metrics to identify co-moving metrics.

**3\.** Run calculate\_lag\_correlation to detect leading indicators.

**4\.** Run decompose\_impact\_by\_dimension for segment breakdown.

**5\.** Assemble all results into a single JSONB document.

 

**💾  SQL**

 

SELECT  
  (payload-\>\>'anomaly\_stats')::JSONB       AS anomaly\_stats,  
  (payload-\>\>'correlations')::JSONB        AS correlations,  
  (payload-\>\>'leading\_indicators')::JSONB  AS leading\_indicators,  
  (payload-\>\>'impact\_by\_segment')::JSONB   AS impact\_by\_segment  
FROM (  
  SELECT build\_anomaly\_explanation\_payload(  
    'revenue',          \-- primary metric  
    '2024-01-15'::DATE, \-- anomaly date  
    14                  \-- lookback days  
  ) AS payload  
) sub;  
 

**📊  Source Table: metrics\_daily**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| metric\_date | DATE | 2024-01-15 |
| metric\_name | TEXT | revenue |
| metric\_value | DECIMAL | 84000.00 |
| region | TEXT | us-east |
| product\_tier | TEXT | enterprise |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| anomaly\_stats | {"metric":"revenue","z\_score":-3.2,"pct\_deviation":"-32.8%"} |
| correlations | \[{"metric":"p99\_latency\_ms","correlation":-0.89}\] |
| leading\_indicators | \[{"metric":"p99\_latency\_ms","lag":-2}\] |
| impact\_by\_segment | \[{"segment":"us-east/enterprise","contribution":"58.3%"}\] |

 

 

# **2\. Impact Calculation**

 

**Example 2.1 — calculate\_generic\_impact / build\_impact\_parameter**

**❓  Natural Language Question**

*Score the business impact of a critical production database compromise, weighing asset criticality, data sensitivity, and number of dependent services.*

 

**📋  Description**

Uses build\_impact\_parameter to construct typed parameter objects (direct, indirect, cascading) and then feeds them to calculate\_generic\_impact with weighted\_sum aggregation. Returns an overall impact score out of 100 plus a breakdown by impact category.

**🔢  Steps**

**1\.** Build a 'criticality' direct parameter (value=95, weight=0.40).

**2\.** Build a 'data\_sensitivity' direct parameter (value=88, weight=0.35).

**3\.** Build a 'dependent\_services' cascading parameter (value=18, max=50, weight=0.25).

**4\.** Feed the array to calculate\_generic\_impact using weighted\_sum aggregation with cascade enabled.

 

**💾  SQL**

 

SELECT  
  overall\_impact,  
  direct\_impact,  
  cascading\_impact,  
  aggregation\_method,  
  impact\_by\_category,  
  parameter\_scores  
FROM calculate\_generic\_impact(  
  ARRAY\[  
    build\_impact\_parameter('criticality',         95, 0.40, 100, 'direct'),  
    build\_impact\_parameter('data\_sensitivity',    88, 0.35, 100, 'direct'),  
    build\_impact\_parameter('dependent\_services',  18, 0.25,  50, 'cascading')  
  \],  
  'weighted\_sum',  \-- aggregation method  
  100.0,           \-- scale to  
  TRUE,            \-- enable cascade  
  3                \-- cascade depth  
);  
 

**📊  Source Table: No source table — parameters passed inline**

 

*No source table — parameters passed inline — all parameters supplied inline.*

| Parameter | Type / Source | Example Value |
| ----- | ----- | ----- |
| param\_name | TEXT | criticality |
| param\_value | DECIMAL | 95 |
| param\_weight | DECIMAL | 0.40 |
| max\_value | DECIMAL | 100 |
| impact\_category | TEXT | direct |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| overall\_impact | 87.3 |
| direct\_impact | 72.1 |
| cascading\_impact | 15.2 |
| aggregation\_method | weighted\_sum |
| impact\_by\_category | {"direct":72.1,"cascading":15.2} |
| parameter\_scores | {"criticality":38.0,"data\_sensitivity":30.8,"dependent\_services":9.0} |

 

 

**Example 2.2 — calculate\_impact\_from\_json**

**❓  Natural Language Question**

*Score the impact of a ransomware attack on a file server using a JSON config — suitable for API-driven or LLM-generated input.*

 

**📋  Description**

Accepts a JSONB config instead of typed parameter arrays. Ideal for dynamic pipelines where parameters are assembled at runtime by an orchestrator or LLM. Returns the same rich output as calculate\_generic\_impact.

**🔢  Steps**

**1\.** Construct a JSONB config with aggregation\_method, scale\_to, enable\_cascade flags.

**2\.** Include parameters array with param\_name, param\_value, param\_weight, max\_value, impact\_category.

**3\.** Call calculate\_impact\_from\_json with the config.

**4\.** Inspect overall\_impact and calculation\_summary.

 

**💾  SQL**

 

SELECT  
  overall\_impact,  
  direct\_impact,  
  indirect\_impact,  
  cascading\_impact,  
  aggregation\_method,  
  calculation\_summary  
FROM calculate\_impact\_from\_json(  
  '{  
    "aggregation\_method": "weighted\_sum",  
    "scale\_to": 100,  
    "enable\_cascade": true,  
    "cascade\_depth": 3,  
    "parameters": \[  
      {  
        "param\_name":     "asset\_criticality",  
        "param\_value":    92,  
        "param\_weight":   0.45,  
        "max\_value":      100,  
        "impact\_category":"direct"  
      },  
      {  
        "param\_name":     "data\_loss\_exposure",  
        "param\_value":    75,  
        "param\_weight":   0.35,  
        "max\_value":      100,  
        "impact\_category":"direct"  
      },  
      {  
        "param\_name":     "recovery\_complexity",  
        "param\_value":    30,  
        "param\_weight":   0.20,  
        "max\_value":      50,  
        "impact\_category":"indirect"  
      }  
    \]  
  }'::JSONB  
);  
 

**📊  Source Table: No source table — config passed as JSONB**

 

*No source table — config passed as JSONB — all parameters supplied inline.*

| Parameter | Type / Source | Example Value |
| ----- | ----- | ----- |
| param\_name | TEXT (JSONB key) | asset\_criticality |
| param\_value | NUMERIC (JSONB) | 92 |
| param\_weight | NUMERIC (JSONB) | 0.45 |
| max\_value | NUMERIC (JSONB) | 100 |
| impact\_category | TEXT (JSONB) | direct |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| overall\_impact | 83.7 |
| direct\_impact | 68.4 |
| indirect\_impact | 12.0 |
| cascading\_impact | 3.3 |
| aggregation\_method | weighted\_sum |
| calculation\_summary | {"parameters\_used":3,"scale\_to":100} |

 

 

**Example 2.3 — calculate\_cascading\_impact**

**❓  Natural Language Question**

*A core authentication service is compromised. Estimate the blast radius across 15 downstream systems over 3 dependency tiers.*

 

**📋  Description**

Models ripple effects from a primary compromise through dependent systems. Each tier receives a fraction (cascade\_rate) of the previous tier's impact. Returns primary, secondary, and tertiary impacts plus a blast\_radius\_score.

**🔢  Steps**

**1\.** Set primary impact score to 78.0 (from a prior impact calculation).

**2\.** Specify 15 affected downstream systems.

**3\.** Set dependency depth to 3 tiers and cascade rate to 0.50.

**4\.** Review blast\_radius\_score for total systemic exposure.

 

**💾  SQL**

 

SELECT  
  primary\_impact,  
  secondary\_impact,  
  tertiary\_impact,  
  total\_cascaded\_impact,  
  affected\_systems,  
  blast\_radius\_score  
FROM calculate\_cascading\_impact(  
  78.0,   \-- primary impact score  
  15,     \-- affected downstream systems  
  3,      \-- dependency depth (tiers)  
  0.50    \-- cascade rate per tier  
);  
 

**📊  Source Table: No source table — scalar parameters**

 

*No source table — scalar parameters — all parameters supplied inline.*

| Parameter | Type / Source | Example Value |
| ----- | ----- | ----- |
| p\_primary\_impact | DECIMAL | 78.0 |
| p\_affected\_systems\_count | INTEGER | 15 |
| p\_dependency\_depth | INTEGER | 3 |
| p\_cascade\_rate | DECIMAL | 0.50 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| primary\_impact | 78.0 |
| secondary\_impact | 39.0 |
| tertiary\_impact | 19.5 |
| total\_cascaded\_impact | 136.5 |
| affected\_systems | 15 |
| blast\_radius\_score | 91.0 |

 

 

**Example 2.4 — classify\_impact\_level**

**❓  Natural Language Question**

*Given a composite impact score of 83.7, what action tier does this fall into and what is the recommended response?*

 

**📋  Description**

Maps a numeric impact score to a classification tier (CRITICAL / HIGH / MEDIUM / LOW / MINIMAL) with a recommended action. Standard thresholds: CRITICAL\>=90, HIGH\>=70, MEDIUM\>=50, LOW\>=30.

**🔢  Steps**

**1\.** Pass the computed impact score (83.7) to classify\_impact\_level.

**2\.** Optionally override thresholds for organisation-specific calibration.

**3\.** Read impact\_level, impact\_category, priority\_order, and recommended\_action.

 

**💾  SQL**

 

SELECT  
  impact\_score,  
  impact\_level,  
  impact\_category,  
  priority\_order,  
  recommended\_action  
FROM classify\_impact\_level(  
  83.7,   \-- impact score from calculate\_generic\_impact  
  90.0,   \-- critical threshold (default 90\)  
  70.0,   \-- high threshold (default 70\)  
  50.0,   \-- medium threshold (default 50\)  
  30.0    \-- low threshold (default 30\)  
);  
 

**📊  Source Table: No source table — single scalar input**

 

*No source table — single scalar input — all parameters supplied inline.*

| Parameter | Type / Source | Example Value |
| ----- | ----- | ----- |
| p\_impact\_score | DECIMAL | 83.7 |
| p\_threshold\_critical | DECIMAL | 90.0 |
| p\_threshold\_high | DECIMAL | 70.0 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| impact\_score | 83.7 |
| impact\_level | HIGH |
| impact\_category | Significant business impact |
| priority\_order | 2 |
| recommended\_action | Escalate to security lead; initiate IR playbook within 2 hours |

 

 

**Example 2.5 — calculate\_impact\_batch**

**❓  Natural Language Question**

*Score and rank the business impact across five critical assets simultaneously for an executive dashboard.*

 

**📋  Description**

Batch-scores multiple assets in a single call using per-asset parameter arrays. Returns ranked results with percentiles, enabling direct use as a risk register sorted by impact.

**🔢  Steps**

**1\.** Construct a JSONB array — one entry per asset, each with its own parameters.

**2\.** Call calculate\_impact\_batch with the array.

**3\.** Order results by rank\_overall to surface the highest-risk assets.

 

**💾  SQL**

 

SELECT  
  asset\_id,  
  overall\_impact,  
  direct\_impact,  
  cascading\_impact,  
  impact\_level,  
  rank\_overall,  
  percentile  
FROM calculate\_impact\_batch(  
  '\[  
    {  
      "asset\_id": "db-prod-auth-01",  
      "aggregation\_method": "weighted\_sum",  
      "enable\_cascade": true,  
      "parameters": \[  
        {"param\_name":"criticality",  "param\_value":95,"param\_weight":0.60,"impact\_category":"direct"},  
        {"param\_name":"dependencies", "param\_value":22,"param\_weight":0.40,"max\_value":50,"impact\_category":"cascading"}  
      \]  
    },  
    {  
      "asset\_id": "api-gateway-prod",  
      "aggregation\_method": "weighted\_sum",  
      "enable\_cascade": true,  
      "parameters": \[  
        {"param\_name":"criticality",  "param\_value":80,"param\_weight":0.60,"impact\_category":"direct"},  
        {"param\_name":"dependencies", "param\_value":35,"param\_weight":0.40,"max\_value":50,"impact\_category":"cascading"}  
      \]  
    }  
  \]'::JSONB  
)  
ORDER BY rank\_overall;  
 

**📊  Source Table: No source table — JSONB array input**

 

*No source table — JSONB array input — all parameters supplied inline.*

| Parameter | Type / Source | Example Value |
| ----- | ----- | ----- |
| asset\_id | TEXT (JSONB) | db-prod-auth-01 |
| param\_name | TEXT (JSONB) | criticality |
| param\_value | NUMERIC | 95 |
| param\_weight | NUMERIC | 0.60 |
| impact\_category | TEXT | direct |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| asset\_id | db-prod-auth-01 |
| overall\_impact | 88.4 |
| direct\_impact | 57.0 |
| cascading\_impact | 17.6 |
| impact\_level | HIGH |
| rank\_overall | 1 |
| percentile | 95.0 |

 

 

# **3\. Likelihood Calculation**

 

**Example 3.1 — calculate\_vulnerability\_likelihood**

**❓  Natural Language Question**

*What is the likelihood of exploitation for a server with 3 critical, 8 high, and 15 medium open vulnerabilities?*

 

**📋  Description**

Computes a likelihood score from vulnerability counts weighted by severity. Critical vulns have the highest contribution; medium and low contribute progressively less. Returns per-severity contributions enabling remediation prioritization.

**🔢  Steps**

**1\.** Pass vulnerability counts by severity in a JSONB config.

**2\.** Function applies CVSS-aligned weights: critical=40%, high=30%, medium=20%, low=10%.

**3\.** Sum weighted contributions and normalize to 0-100 scale.

**4\.** Interpret likelihood\_score and per-severity contributions.

 

**💾  SQL**

 

SELECT  
  likelihood\_score,  
  critical\_vuln\_contribution,  
  high\_vuln\_contribution,  
  medium\_vuln\_contribution,  
  low\_vuln\_contribution  
FROM calculate\_vulnerability\_likelihood(  
  '{  
    "critical\_vuln\_count": 3,  
    "high\_vuln\_count":     8,  
    "medium\_vuln\_count":  15,  
    "low\_vuln\_count":      4  
  }'::JSONB  
);  
 

**📊  Source Table: risk\_impact\_metadata (or inline JSONB)**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| critical\_vuln\_count | INTEGER (JSONB) | 3 |
| high\_vuln\_count | INTEGER (JSONB) | 8 |
| medium\_vuln\_count | INTEGER (JSONB) | 15 |
| low\_vuln\_count | INTEGER (JSONB) | 4 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| likelihood\_score | 72.4 |
| critical\_vuln\_contribution | 31.5 |
| high\_vuln\_contribution | 26.0 |
| medium\_vuln\_contribution | 12.5 |
| low\_vuln\_contribution | 2.4 |

 

 

**Example 3.2 — calculate\_time\_weighted\_likelihood**

**❓  Natural Language Question**

*An unpatched CVE has been present for 45 days and the SLA deadline is in 5 days. How does time pressure affect breach likelihood?*

 

**📋  Description**

Combines dwell time (how long a vulnerability has been present) with urgency (days remaining until SLA deadline) using exponential decay. Longer dwell time and approaching deadlines both amplify likelihood.

**🔢  Steps**

**1\.** Set dwell\_time\_days=45 (vulnerability age) and days\_until\_due=5 (SLA pressure).

**2\.** Exponential decay amplifies likelihood as dwell\_time grows.

**3\.** Urgency factor spikes as days\_until\_due approaches zero.

**4\.** Review urgency\_factor, dwell\_time\_penalty, and final likelihood\_score.

 

**💾  SQL**

 

SELECT  
  likelihood\_score,  
  urgency\_factor,  
  dwell\_time\_penalty,  
  time\_to\_due\_bonus,  
  exponential\_decay  
FROM calculate\_time\_weighted\_likelihood(  
  '{  
    "dwell\_time\_days":  45,  
    "days\_until\_due":    5,  
    "tau\_zero":         30,  
    "base\_likelihood":  50  
  }'::JSONB  
);  
 

**📊  Source Table: risk\_impact\_metadata (or inline JSONB)**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| dwell\_time\_days | INTEGER | 45 |
| days\_until\_due | INTEGER | 5 |
| tau\_zero | INTEGER | 30 |
| base\_likelihood | DECIMAL | 50 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| likelihood\_score | 81.2 |
| urgency\_factor | 1.45 |
| dwell\_time\_penalty | 22.1 |
| time\_to\_due\_bonus | 9.1 |
| exponential\_decay | 0.78 |

 

 

**Example 3.3 — calculate\_asset\_likelihood**

**❓  Natural Language Question**

*Compute a holistic breach likelihood score for asset 'db-prod-auth-01', combining its vulnerability posture, behavioral signals, and time pressure.*

 

**📋  Description**

Aggregates all likelihood dimensions for a single asset — vulnerability counts, behavioral indicators (login anomalies, incident history), time-weighted urgency, and exposure factors. Returns a composite likelihood plus sub-scores for each dimension.

**🔢  Steps**

**1\.** Provide asset\_id and a JSONB config with all relevant parameters.

**2\.** Function internally calls calculate\_vulnerability\_likelihood, calculate\_behavioral\_likelihood, and calculate\_time\_weighted\_likelihood.

**3\.** Weights sub-scores by vulnerability (40%), exposure (30%), behavioral (20%), time (10%).

**4\.** Return total\_likelihood and component breakdown.

 

**💾  SQL**

 

SELECT  
  asset\_id,  
  total\_likelihood,  
  vulnerability\_likelihood,  
  exposure\_likelihood,  
  behavioral\_likelihood,  
  time\_weighted\_likelihood  
FROM calculate\_asset\_likelihood(  
  'db-prod-auth-01',  
  '{  
    "critical\_vuln\_count":    3,  
    "high\_vuln\_count":        8,  
    "medium\_vuln\_count":     15,  
    "dwell\_time\_days":       45,  
    "days\_until\_due":         5,  
    "risky\_login\_attempts":  12,  
    "past\_incidents":         2,  
    "internet\_exposed":    true,  
    "encryption\_at\_rest": false  
  }'::JSONB  
);  
 

**📊  Source Table: risk\_impact\_metadata**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| asset\_id | TEXT | db-prod-auth-01 |
| critical\_vuln\_count | INTEGER | 3 |
| risky\_login\_attempts | INTEGER | 12 |
| dwell\_time\_days | INTEGER | 45 |
| internet\_exposed | BOOLEAN | true |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| asset\_id | db-prod-auth-01 |
| total\_likelihood | 76.8 |
| vulnerability\_likelihood | 72.4 |
| exposure\_likelihood | 81.0 |
| behavioral\_likelihood | 68.5 |
| time\_weighted\_likelihood | 81.2 |

 

 

**Example 3.4 — calculate\_likelihood\_trend**

**❓  Natural Language Question**

*Is this asset's breach likelihood getting better or worse over the past 90 days, and what will it look like in 30 days?*

 

**📋  Description**

Analyzes historical likelihood scores over 30/60/90-day windows to compute trend direction, velocity, and a 30-day forecast. Surfaces assets whose risk is trending upward before it becomes critical.

**🔢  Steps**

**1\.** Retrieve historical likelihood snapshots from a scores table.

**2\.** Compute moving averages for 30d, 60d, 90d windows.

**3\.** Fit a linear trend to calculate trend\_direction and trend\_percentage\_change.

**4\.** Extrapolate 30-day forecast using the trend slope.

 

**💾  SQL**

 

SELECT  
  asset\_id,  
  current\_likelihood,  
  avg\_likelihood\_30d,  
  avg\_likelihood\_60d,  
  avg\_likelihood\_90d,  
  trend\_direction,  
  trend\_percentage\_change,  
  forecast\_30d  
FROM calculate\_likelihood\_trend(  
  'db-prod-auth-01',  
  90  \-- lookback days  
);  
 

**📊  Source Table: likelihood\_scores (historical snapshots)**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| asset\_id | TEXT | db-prod-auth-01 |
| score\_date | DATE | 2024-01-01 |
| likelihood\_score | DECIMAL | 64.2 |
| score\_type | TEXT | composite |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| asset\_id | db-prod-auth-01 |
| current\_likelihood | 76.8 |
| avg\_likelihood\_30d | 72.1 |
| avg\_likelihood\_60d | 65.4 |
| avg\_likelihood\_90d | 58.3 |
| trend\_direction | INCREASING |
| trend\_percentage\_change | \+31.7% |
| forecast\_30d | 84.2 |

 

 

# **4\. Moving Averages**

 

**Example 4.1 — calculate\_sma**

**❓  Natural Language Question**

*Smooth daily p99 latency over a 7-day rolling window and flag days where latency exceeds 2 standard deviations from the moving average.*

 

**📋  Description**

Computes a Simple Moving Average with Bollinger-style bands (±2 std dev). The deviation and percent\_deviation columns indicate how far each day's value sits from the smoothed baseline. Values outside the bands are anomaly candidates.

**🔢  Steps**

**1\.** Prepare a JSONB array of {time\_period, value} pairs from the metrics table.

**2\.** Call calculate\_sma with window\_size=7.

**3\.** Filter rows where original\_value \> upper\_band to find spikes.

**4\.** Use percent\_deviation to rank severity of individual anomalies.

 

**💾  SQL**

 

WITH latency\_series AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', metric\_date, 'value', metric\_value)  
    ORDER BY metric\_date  
  ) AS data  
  FROM metrics\_daily  
  WHERE metric\_name \= 'p99\_latency\_ms'  
    AND metric\_date BETWEEN '2024-01-01' AND '2024-01-31'  
)  
SELECT  
  time\_period,  
  original\_value,  
  sma\_value,  
  upper\_band,  
  lower\_band,  
  percent\_deviation,  
  CASE WHEN original\_value \> upper\_band THEN 'SPIKE' ELSE 'normal' END AS status  
FROM latency\_series,  
     calculate\_sma(latency\_series.data, 7\)  \-- window\_size \= 7  
WHERE original\_value \> upper\_band  
ORDER BY time\_period;  
 

**📊  Source Table: metrics\_daily**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| metric\_date | DATE | 2024-01-15 |
| metric\_name | TEXT | p99\_latency\_ms |
| metric\_value | DECIMAL | 4320.00 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| time\_period | 2024-01-15 |
| original\_value | 4320.00 |
| sma\_value | 2180.00 |
| upper\_band | 3140.00 |
| lower\_band | 1220.00 |
| percent\_deviation | \+98.2% |
| status | SPIKE |

 

 

**Example 4.2 — calculate\_bollinger\_bands**

**❓  Natural Language Question**

*Apply Bollinger Bands to daily vulnerability scan counts to identify sustained high-risk periods vs. normal variance.*

 

**📋  Description**

Computes SMA ± N standard deviations and adds bandwidth (spread between bands) and %B (position of value within the bands). %B \> 1.0 means above upper band; %B \< 0.0 means below lower band.

**🔢  Steps**

**1\.** Aggregate daily vulnerability scan counts into a JSONB array.

**2\.** Call calculate\_bollinger\_bands with window=14, num\_std\_dev=2.

**3\.** Filter for %B \> 1.0 (above upper band) — sustained elevated risk periods.

**4\.** Use bandwidth to measure volatility: wider bands \= more uncertain environment.

 

**💾  SQL**

 

WITH vuln\_series AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', scan\_date, 'value', open\_vuln\_count)  
    ORDER BY scan\_date  
  ) AS data  
  FROM daily\_vuln\_summary  
  WHERE asset\_group \= 'prod-infra'  
    AND scan\_date BETWEEN '2023-10-01' AND '2024-01-31'  
)  
SELECT  
  time\_period,  
  original\_value,  
  middle\_band,  
  upper\_band,  
  lower\_band,  
  bandwidth,  
  percent\_b,  
  CASE  
    WHEN percent\_b \> 1.0 THEN 'ABOVE\_BAND'  
    WHEN percent\_b \< 0.0 THEN 'BELOW\_BAND'  
    ELSE 'within\_bands'  
  END AS band\_position  
FROM vuln\_series,  
     calculate\_bollinger\_bands(vuln\_series.data, 14, 2\)  
ORDER BY time\_period;  
 

**📊  Source Table: daily\_vuln\_summary**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| scan\_date | DATE | 2024-01-15 |
| asset\_group | TEXT | prod-infra |
| open\_vuln\_count | INTEGER | 847 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| time\_period | 2024-01-15 |
| original\_value | 847 |
| middle\_band | 612.4 |
| upper\_band | 781.2 |
| lower\_band | 443.6 |
| bandwidth | 337.6 |
| percent\_b | 1.12 |
| band\_position | ABOVE\_BAND |

 

 

**Example 4.3 — calculate\_moving\_correlation**

**❓  Natural Language Question**

*Is the historical relationship between CPU utilization and error rate strengthening or weakening over time?*

 

**📋  Description**

Computes a rolling Pearson correlation between two time series over a sliding window. Detects regime changes — periods where a previously tight relationship breaks down, which can indicate infrastructure or architectural changes.

**🔢  Steps**

**1\.** Build two parallel JSONB arrays: cpu\_util and error\_rate, aligned by date.

**2\.** Call calculate\_moving\_correlation with window=14.

**3\.** Observe how correlation\_strength changes over time.

**4\.** Flag windows where correlation drops below 0.3 (relationship breakdown).

 

**💾  SQL**

 

WITH cpu\_series AS (  
  SELECT json\_agg(json\_build\_object('time\_period', metric\_date, 'value', metric\_value) ORDER BY metric\_date) AS cpu\_data  
  FROM metrics\_daily WHERE metric\_name \= 'cpu\_utilization'  
),  
error\_series AS (  
  SELECT json\_agg(json\_build\_object('time\_period', metric\_date, 'value', metric\_value) ORDER BY metric\_date) AS err\_data  
  FROM metrics\_daily WHERE metric\_name \= 'error\_rate\_pct'  
)  
SELECT  
  time\_period,  
  value\_x         AS cpu\_utilization,  
  value\_y         AS error\_rate,  
  correlation,  
  correlation\_strength  
FROM cpu\_series, error\_series,  
     calculate\_moving\_correlation(cpu\_series.cpu\_data, error\_series.err\_data, 14\)  
ORDER BY time\_period;  
 

**📊  Source Table: metrics\_daily**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| metric\_date | DATE | 2024-01-15 |
| metric\_name | TEXT | cpu\_utilization |
| metric\_value | DECIMAL | 84.3 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| time\_period | 2024-01-15 |
| cpu\_utilization | 84.3 |
| error\_rate | 3.21 |
| correlation | 0.847 |
| correlation\_strength | strong\_positive |

 

 

# **5\. Time Series Analysis**

 

**Example 5.1 — calculate\_autocorrelation**

**❓  Natural Language Question**

*Does daily login failure count show weekly periodicity? Test autocorrelation up to lag 14\.*

 

**📋  Description**

Computes the Autocorrelation Function (ACF) for up to N lags. Significant autocorrelation at lag 7 confirms weekly seasonality; at lag 1 it indicates persistence (yesterday's value predicts today's). Returns confidence bounds for significance testing.

**🔢  Steps**

**1\.** Aggregate daily failed login counts into a JSONB array.

**2\.** Call calculate\_autocorrelation with max\_lag=14.

**3\.** Identify lags where is\_significant \= true.

**4\.** Spikes at lag 7 and 14 confirm weekly seasonality.

 

**💾  SQL**

 

WITH login\_fails AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', event\_date, 'value', fail\_count)  
    ORDER BY event\_date  
  ) AS data  
  FROM daily\_auth\_events  
  WHERE event\_date BETWEEN '2023-07-01' AND '2024-01-31'  
)  
SELECT  
  lag\_period,  
  autocorrelation,  
  is\_significant,  
  confidence\_lower,  
  confidence\_upper  
FROM login\_fails,  
     calculate\_autocorrelation(login\_fails.data, 14\)  
WHERE is\_significant \= true  
ORDER BY lag\_period;  
 

**📊  Source Table: daily\_auth\_events**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| event\_date | DATE | 2024-01-15 |
| fail\_count | INTEGER | 284 |
| event\_type | TEXT | login\_failure |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| lag\_period | 7 |
| autocorrelation | 0.734 |
| is\_significant | true |
| confidence\_lower | \-0.138 |
| confidence\_upper | 0.138 |

 

 

**Example 5.2 — test\_stationarity**

**❓  Natural Language Question**

*Before feeding threat score history into a forecasting model, check whether the series is stationary.*

 

**📋  Description**

Tests mean stability, variance stability, and trend significance to determine stationarity. A non-stationary series (trending or variance-changing) needs differencing or transformation before forecasting. Returns actionable recommendations.

**🔢  Steps**

**1\.** Prepare the threat score time series as a JSONB array.

**2\.** Call test\_stationarity to run mean, variance, and trend tests.

**3\.** If is\_stationary \= false, apply calculate\_difference to make it stationary.

**4\.** Pass the recommendation to the data engineering pipeline.

 

**💾  SQL**

 

WITH threat\_series AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', score\_date, 'value', threat\_score)  
    ORDER BY score\_date  
  ) AS data  
  FROM asset\_threat\_scores  
  WHERE asset\_id \= 'db-prod-auth-01'  
    AND score\_date \>= CURRENT\_DATE \- INTERVAL '90 days'  
)  
SELECT  
  test\_name,  
  is\_stationary,  
  mean\_value,  
  variance,  
  trend\_slope,  
  recommendation  
FROM threat\_series,  
     test\_stationarity(threat\_series.data);  
 

**📊  Source Table: asset\_threat\_scores**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| score\_date | DATE | 2024-01-15 |
| asset\_id | TEXT | db-prod-auth-01 |
| threat\_score | DECIMAL | 72.4 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| test\_name | trend\_stability |
| is\_stationary | false |
| mean\_value | 68.3 |
| variance | 124.7 |
| trend\_slope | \+0.42 |
| recommendation | Apply first differencing; series shows upward trend |

 

 

**Example 5.3 — analyze\_distribution**

**❓  Natural Language Question**

*Compare the distribution of remediation times between enterprise and SMB tiers to understand if SLAs are being met differently.*

 

**📋  Description**

Computes per-group distribution statistics including mean, median, std dev, skewness, and kurtosis. Groups with high positive skew have a long tail of very slow remediations that inflate averages and mask SLA risk.

**🔢  Steps**

**1\.** Provide remediation time data with a product\_tier grouping column.

**2\.** Call analyze\_distribution with group\_field \= 'product\_tier'.

**3\.** Compare median vs mean — large gaps indicate skewed distributions.

**4\.** Use skewness and kurtosis to characterize tail risk.

 

**💾  SQL**

 

WITH remediation\_data AS (  
  SELECT json\_agg(  
    json\_build\_object(  
      'time\_period', closed\_date,  
      'value',       days\_to\_close,  
      'group',       product\_tier  
    )  
    ORDER BY closed\_date  
  ) AS data  
  FROM vulnerability\_tickets  
  WHERE closed\_date \>= '2023-01-01'  
    AND severity \= 'CRITICAL'  
)  
SELECT  
  group\_name      AS product\_tier,  
  count\_values,  
  mean\_value      AS avg\_days\_to\_close,  
  median\_value,  
  std\_dev,  
  skewness,  
  kurtosis,  
  min\_value,  
  max\_value  
FROM remediation\_data,  
     analyze\_distribution(remediation\_data.data, 'group')  
ORDER BY mean\_value DESC;  
 

**📊  Source Table: vulnerability\_tickets**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| closed\_date | DATE | 2024-01-15 |
| days\_to\_close | INTEGER | 12 |
| severity | TEXT | CRITICAL |
| product\_tier | TEXT | enterprise |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| product\_tier | enterprise |
| count\_values | 312 |
| avg\_days\_to\_close | 8.4 |
| median\_value | 5.0 |
| std\_dev | 11.2 |
| skewness | 2.8 |
| kurtosis | 9.1 |

 

 

# **6\. Trend Analysis**

 

**Example 6.1 — calculate\_statistical\_trend**

**❓  Natural Language Question**

*Is the number of open critical vulnerabilities trending up or down over the last quarter? Is the trend statistically significant?*

 

**📋  Description**

Fits an OLS linear regression to the time series. Returns slope (rate of change per period), R-squared (model fit), and a p-value for significance. A negative slope with p \< 0.05 confirms a statistically meaningful decline in open criticals.

**🔢  Steps**

**1\.** Build a JSONB array of daily open critical vuln counts.

**2\.** Call calculate\_statistical\_trend.

**3\.** Check is\_significant and slope direction.

**4\.** Use r\_squared to assess how well the linear model explains the trend.

 

**💾  SQL**

 

WITH open\_criticals AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', scan\_date, 'value', critical\_count)  
    ORDER BY scan\_date  
  ) AS data  
  FROM daily\_vuln\_summary  
  WHERE scan\_date \>= CURRENT\_DATE \- INTERVAL '90 days'  
)  
SELECT  
  trend\_direction,  
  slope,  
  intercept,  
  r\_squared,  
  correlation,  
  p\_value,  
  is\_significant,  
  data\_points  
FROM open\_criticals,  
     calculate\_statistical\_trend(open\_criticals.data);  
 

**📊  Source Table: daily\_vuln\_summary**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| scan\_date | DATE | 2024-01-15 |
| critical\_count | INTEGER | 47 |
| asset\_group | TEXT | prod-infra |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| trend\_direction | DECREASING |
| slope | \-0.42 |
| intercept | 61.3 |
| r\_squared | 0.87 |
| correlation | \-0.93 |
| p\_value | 0.0001 |
| is\_significant | true |
| data\_points | 90 |

 

 

**Example 6.2 — forecast\_linear**

**❓  Natural Language Question**

*Based on the current remediation velocity, how many open critical vulnerabilities will remain in 30 days?*

 

**📋  Description**

Extends the linear trend model to produce forecasts for N future periods. Uses the fitted slope and intercept to extrapolate, with confidence intervals derived from historical residual variance.

**🔢  Steps**

**1\.** Supply the same historical data used in calculate\_statistical\_trend.

**2\.** Set forecast\_periods=30 for a 30-day horizon.

**3\.** Review forecast\_value and confidence bounds at day 30\.

**4\.** Use lower\_bound/upper\_bound for SLA risk scenario planning.

 

**💾  SQL**

 

WITH open\_criticals AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', scan\_date, 'value', critical\_count)  
    ORDER BY scan\_date  
  ) AS data  
  FROM daily\_vuln\_summary  
  WHERE scan\_date \>= CURRENT\_DATE \- INTERVAL '90 days'  
)  
SELECT  
  forecast\_period,  
  forecast\_date,  
  forecast\_value,  
  lower\_bound,  
  upper\_bound  
FROM open\_criticals,  
     forecast\_linear(open\_criticals.data, 30\)  
ORDER BY forecast\_period;  
 

**📊  Source Table: daily\_vuln\_summary**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| scan\_date | DATE | 2024-01-15 |
| critical\_count | INTEGER | 47 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| forecast\_period | 30 |
| forecast\_date | 2024-02-15 |
| forecast\_value | 34.4 |
| lower\_bound | 28.1 |
| upper\_bound | 40.7 |

 

 

**Example 6.3 — detect\_anomalies**

**❓  Natural Language Question**

*Automatically flag days where login failure counts are statistically anomalous over the past 90 days.*

 

**📋  Description**

Uses a rolling z-score approach to identify outlier observations in a time series. Any point beyond ±N standard deviations from the rolling mean is flagged. Returns anomaly\_score and anomaly classification for each data point.

**🔢  Steps**

**1\.** Build a JSONB array of daily login failure counts.

**2\.** Call detect\_anomalies with z\_threshold=2.5.

**3\.** Filter for is\_anomaly \= true to return flagged dates.

**4\.** Order by anomaly\_score DESC to prioritize the most extreme events.

 

**💾  SQL**

 

WITH login\_data AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', event\_date, 'value', fail\_count)  
    ORDER BY event\_date  
  ) AS data  
  FROM daily\_auth\_events  
  WHERE event\_date \>= CURRENT\_DATE \- INTERVAL '90 days'  
)  
SELECT  
  time\_period,  
  original\_value,  
  expected\_value,  
  anomaly\_score,  
  is\_anomaly,  
  anomaly\_type  
FROM login\_data,  
     detect\_anomalies(login\_data.data, 14, 2.5)  
WHERE is\_anomaly \= true  
ORDER BY anomaly\_score DESC;  
 

**📊  Source Table: daily\_auth\_events**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| event\_date | DATE | 2024-01-15 |
| fail\_count | INTEGER | 284 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| time\_period | 2024-01-15 |
| original\_value | 1847 |
| expected\_value | 312.4 |
| anomaly\_score | 4.91 |
| is\_anomaly | true |
| anomaly\_type | spike |

 

 

**Example 6.4 — detect\_seasonality**

**❓  Natural Language Question**

*Does our weekly security alert volume show day-of-week seasonality that we should account for in our alert thresholds?*

 

**📋  Description**

Groups time series data by a seasonal period (e.g., day\_of\_week, hour\_of\_day, month) and computes the seasonal index for each group. A seasonal index \> 1.0 means that period tends to be above the global average.

**🔢  Steps**

**1\.** Supply daily alert count data as a JSONB array.

**2\.** Call detect\_seasonality with period='day\_of\_week'.

**3\.** Seasonal indices above 1.2 indicate materially elevated days.

**4\.** Use seasonal\_index to adjust alert thresholds dynamically per day.

 

**💾  SQL**

 

WITH alert\_data AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', alert\_date, 'value', alert\_count)  
    ORDER BY alert\_date  
  ) AS data  
  FROM daily\_security\_alerts  
  WHERE alert\_date \>= '2023-01-01'  
)  
SELECT  
  season\_period,  
  period\_avg,  
  global\_avg,  
  seasonal\_index,  
  above\_average  
FROM alert\_data,  
     detect\_seasonality(alert\_data.data, 'day\_of\_week')  
ORDER BY seasonal\_index DESC;  
 

**📊  Source Table: daily\_security\_alerts**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| alert\_date | DATE | 2024-01-15 |
| alert\_count | INTEGER | 542 |
| alert\_type | TEXT | intrusion\_detection |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| season\_period | Monday |
| period\_avg | 682.4 |
| global\_avg | 512.3 |
| seasonal\_index | 1.332 |
| above\_average | true |

 

 

# **7\. A/B Testing & Operations**

 

**Example 7.1 — calculate\_percent\_change\_comparison**

**❓  Natural Language Question**

*Did deploying a new WAF ruleset (treatment) reduce error rates compared to the control group?*

 

**📋  Description**

Computes treatment vs. baseline percent change, relative uplift, and absolute difference. Designed for A/B test evaluation where control and treatment groups are labeled in a condition column.

**🔢  Steps**

**1\.** Label rows with condition='treatment' (new WAF) or condition='control' (old rules).

**2\.** Supply data as a JSONB array with time\_period, value, and condition fields.

**3\.** Call calculate\_percent\_change\_comparison.

**4\.** Review percent\_change and relative\_uplift for the treatment group.

 

**💾  SQL**

 

WITH waf\_experiment AS (  
  SELECT json\_agg(  
    json\_build\_object(  
      'time\_period', metric\_date,  
      'value',       error\_rate,  
      'condition',   experiment\_group  
    )  
    ORDER BY metric\_date  
  ) AS data  
  FROM waf\_ab\_experiment  
  WHERE experiment\_id \= 'waf-ruleset-v3'  
    AND metric\_date BETWEEN '2024-01-01' AND '2024-01-31'  
)  
SELECT  
  condition\_value,  
  metric\_name,  
  baseline\_avg,  
  treatment\_avg,  
  absolute\_change,  
  percent\_change,  
  relative\_uplift  
FROM waf\_experiment,  
     calculate\_percent\_change\_comparison(waf\_experiment.data, 'condition', 'error\_rate')  
ORDER BY condition\_value;  
 

**📊  Source Table: waf\_ab\_experiment**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| metric\_date | DATE | 2024-01-15 |
| error\_rate | DECIMAL | 2.14 |
| experiment\_group | TEXT | treatment |
| experiment\_id | TEXT | waf-ruleset-v3 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| condition\_value | treatment |
| metric\_name | error\_rate |
| baseline\_avg | 3.82 |
| treatment\_avg | 2.14 |
| absolute\_change | \-1.68 |
| percent\_change | \-44.0% |
| relative\_uplift | \-44.0% |

 

 

**Example 7.2 — calculate\_bootstrap\_ci**

**❓  Natural Language Question**

*What are the 95% confidence intervals around mean MTTR (mean time to remediate) for critical vulnerabilities?*

 

**📋  Description**

Bootstrap resampling provides confidence intervals that are robust to non-normal distributions — common in remediation time data, which is typically right-skewed. Returns CI for mean, median, and std dev.

**🔢  Steps**

**1\.** Supply remediation time data as a JSONB array.

**2\.** Call calculate\_bootstrap\_ci with n\_iterations=1000 and confidence=0.95.

**3\.** Read ci\_lower and ci\_upper for the mean estimate.

**4\.** If CI is wide, sample size may be insufficient for reliable SLA commitments.

 

**💾  SQL**

 

WITH mttr\_data AS (  
  SELECT json\_agg(  
    json\_build\_object('time\_period', closed\_date, 'value', days\_to\_close)  
    ORDER BY closed\_date  
  ) AS data  
  FROM vulnerability\_tickets  
  WHERE severity \= 'CRITICAL'  
    AND closed\_date \>= '2023-01-01'  
)  
SELECT  
  metric\_type,  
  point\_estimate,  
  ci\_lower,  
  ci\_upper,  
  confidence\_level,  
  sample\_size  
FROM mttr\_data,  
     calculate\_bootstrap\_ci(mttr\_data.data, 0.95, 1000);  
 

**📊  Source Table: vulnerability\_tickets**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| closed\_date | DATE | 2024-01-15 |
| days\_to\_close | INTEGER | 12 |
| severity | TEXT | CRITICAL |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| metric\_type | mean |
| point\_estimate | 8.4 |
| ci\_lower | 7.1 |
| ci\_upper | 9.8 |
| confidence\_level | 0.95 |
| sample\_size | 312 |

 

 

**Example 7.3 — calculate\_prepost\_comparison**

**❓  Natural Language Question**

*After a security awareness training rollout, did phishing click rates improve?*

 

**📋  Description**

Computes before/after metrics for each entity (department, user group) split by an event cutoff date. Automatically determines the pre/post boundary if not specified. Returns per-entity change direction and magnitude.

**🔢  Steps**

**1\.** Supply time series data with entity\_id (department) and a value (click\_rate).

**2\.** Provide the training rollout date as the cutoff.

**3\.** Call calculate\_prepost\_comparison.

**4\.** Filter for change\_direction \= 'decrease' to identify departments that improved.

 

**💾  SQL**

 

WITH phishing\_data AS (  
  SELECT json\_agg(  
    json\_build\_object(  
      'time\_period', test\_date,  
      'value',       click\_rate\_pct,  
      'entity\_id',   department  
    )  
    ORDER BY test\_date  
  ) AS data  
  FROM phishing\_simulation\_results  
  WHERE test\_date BETWEEN '2023-07-01' AND '2024-01-31'  
)  
SELECT  
  entity\_id           AS department,  
  pre\_value           AS pre\_training\_click\_rate,  
  post\_value          AS post\_training\_click\_rate,  
  absolute\_change,  
  percent\_change,  
  change\_direction  
FROM phishing\_data,  
     calculate\_prepost\_comparison(  
       phishing\_data.data,  
       '2023-10-01'::TIMESTAMP  \-- training rollout date  
     )  
ORDER BY percent\_change;  
 

**📊  Source Table: phishing\_simulation\_results**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| test\_date | DATE | 2024-01-15 |
| department | TEXT | Engineering |
| click\_rate\_pct | DECIMAL | 3.2 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| department | Engineering |
| pre\_training\_click\_rate | 12.4 |
| post\_training\_click\_rate | 3.2 |
| absolute\_change | \-9.2 |
| percent\_change | \-74.2% |
| change\_direction | decrease |

 

 

**Example 7.4 — calculate\_effect\_sizes**

**❓  Natural Language Question**

*How large is the practical effect of our new endpoint detection tool on mean alert resolution time?*

 

**📋  Description**

Computes Cohen's d, Hedges' g, and Glass's delta to measure effect magnitude independent of sample size. Provides interpretations (negligible / small / medium / large) to communicate practical significance alongside statistical p-values.

**🔢  Steps**

**1\.** Supply treatment (new EDR tool) and control (legacy tool) resolution time data.

**2\.** Call calculate\_effect\_sizes.

**3\.** Cohen's d ≥ 0.8 indicates a large practical effect.

**4\.** Report effect\_size\_value and interpretation to stakeholders.

 

**💾  SQL**

 

WITH treatment\_data AS (  
  SELECT json\_agg(json\_build\_object('value', resolution\_minutes)) AS t\_data  
  FROM alert\_resolution WHERE tool\_version \= 'edr\_v2'  
),  
control\_data AS (  
  SELECT json\_agg(json\_build\_object('value', resolution\_minutes)) AS c\_data  
  FROM alert\_resolution WHERE tool\_version \= 'legacy'  
)  
SELECT  
  effect\_size\_type,  
  effect\_size\_value,  
  interpretation,  
  treatment\_mean,  
  control\_mean,  
  pooled\_std  
FROM treatment\_data, control\_data,  
     calculate\_effect\_sizes(  
       treatment\_data.t\_data,  
       control\_data.c\_data  
     );  
 

**📊  Source Table: alert\_resolution**

 

| Column | Data Type | Example Value |
| ----- | ----- | ----- |
| resolution\_minutes | INTEGER | 14 |
| tool\_version | TEXT | edr\_v2 |
| alert\_id | TEXT | ALT-20240115-001 |

 

**📤  Key Output Columns**

 

| Output Column | Sample Value |
| ----- | ----- |
| effect\_size\_type | cohens\_d |
| effect\_size\_value | 0.93 |
| interpretation | large |
| treatment\_mean | 14.2 |
| control\_mean | 38.7 |
| pooled\_std | 26.3 |

 

 

# **Appendix — Function Quick Reference**

 

| Function | Primary Source | One-Line Summary |
| ----- | ----- | ----- |
| find\_correlated\_metrics | metrics\_daily | Pearson correlation ranking for metric pairs around anomaly date |
| calculate\_lag\_correlation | metrics\_daily | Sweep lag positions to find leading indicators |
| decompose\_impact\_by\_dimension | metrics\_daily | Segment contribution decomposition (region/tier) |
| build\_anomaly\_explanation\_payload | metrics\_daily | Full JSONB payload: stats \+ correlations \+ decomposition |
| calculate\_generic\_impact | Inline ARRAY\[\] | Typed parameter array → weighted impact score with cascade |
| calculate\_impact\_from\_json | Inline JSONB | JSON config interface for impact calculation |
| calculate\_impact\_batch | Inline JSONB array | Multi-asset batch scoring with rank and percentile |
| calculate\_cascading\_impact | Scalar params | Blast radius model: primary → secondary → tertiary |
| classify\_impact\_level | Scalar params | Map score to CRITICAL/HIGH/MEDIUM/LOW/MINIMAL |
| build\_impact\_parameter | — | Helper: construct impact\_parameter composite type |
| compare\_impact\_methods | Inline ARRAY\[\] | Compare all aggregation methods on same parameters |
| apply\_impact\_decay\_function | — | Apply decay/growth shape to a single value |
| calculate\_vulnerability\_likelihood | risk\_impact\_metadata / JSONB | Score from CVE counts by severity |
| calculate\_time\_weighted\_likelihood | risk\_impact\_metadata / JSONB | Score from dwell time and SLA pressure |
| calculate\_behavioral\_likelihood | risk\_impact\_metadata / JSONB | Score from login anomalies and incident history |
| calculate\_breach\_likelihood | risk\_impact\_metadata / JSONB | Comprehensive breach score with contributing factors |
| calculate\_asset\_likelihood | risk\_impact\_metadata | Aggregate all likelihood dimensions per asset |
| calculate\_likelihood\_trend | likelihood\_scores | Trend direction and 30-day forecast of likelihood |
| calculate\_likelihood\_batch | Inline JSONB array | Multi-asset batch likelihood with percentile ranking |
| compare\_likelihood\_methods | Inline ARRAY\[\] | Sensitivity analysis across all aggregation methods |
| calculate\_sma | JSONB array | Simple Moving Average with Bollinger bands |
| calculate\_wma | JSONB array | Weighted Moving Average (recent values weighted more) |
| calculate\_ema | JSONB array | Exponential Moving Average with configurable alpha |
| calculate\_bollinger\_bands | JSONB array | SMA ± N std dev bands, bandwidth, and %B position |
| calculate\_moving\_variance | JSONB array | Rolling variance, std dev, CV, and Z-scores |
| calculate\_moving\_quantiles | JSONB array | Moving Q1/median/Q3/IQR for outlier-robust smoothing |
| calculate\_moving\_correlation | Two JSONB arrays | Rolling correlation between two series |
| calculate\_moving\_sum | JSONB array | Rolling sum with contribution % per observation |
| calculate\_moving\_rank | JSONB array | Rolling rank and percentile within window |
| calculate\_moving\_minmax | JSONB array | Rolling min/max/range and position\_in\_range metric |
| calculate\_expanding\_window | JSONB array | Cumulative window (all prior data) for mean/sum/std |
| calculate\_time\_weighted\_ma | JSONB array | Time-weighted MA with exponential decay by recency |
| calculate\_cumulative\_operations | JSONB array | cumsum, cumproduct, cummax, cummin \+ percent\_of\_total |
| calculate\_autocorrelation | JSONB array | ACF up to lag N with significance bounds |
| test\_stationarity | JSONB array | Mean/variance/trend stability tests \+ recommendations |
| analyze\_distribution | JSONB array | Per-group mean, median, skewness, kurtosis |
| analyze\_variance | JSONB array | Rolling/expanding variance with Z-scores |
| calculate\_difference | JSONB array | First and second differences for stationarity |
| calculate\_cdf | JSONB array | Empirical CDF, percentile rank, cumulative probability |
| calculate\_rolling\_window | JSONB array | General rolling aggregation: mean/sum/min/max/std |
| calculate\_lag | JSONB array | Lag shift with absolute/percent change metrics |
| calculate\_lead | JSONB array | Lead shift for forward-looking feature engineering |
| calculate\_percent\_change | JSONB array | Period-over-period % change with magnitude category |
| calculate\_cumulative | JSONB array | Cumulative operations with percent\_of\_total |
| aggregate\_by\_time | JSONB array | Bucket to hour/day/week/month/quarter/year |
| calculate\_growth\_rates | JSONB array | Period-over-period and annualized growth rates |
| calculate\_statistical\_trend | JSONB array | OLS linear regression: slope, R², p-value |
| forecast\_linear | JSONB array | Linear trend extrapolation with confidence bands |
| calculate\_volatility | JSONB array | Historical volatility with rolling std dev |
| compare\_periods | JSONB array | Direct comparison of two time windows |
| detect\_seasonality | JSONB array | Seasonal index by hour/day/week/month |
| detect\_anomalies | JSONB array | Rolling z-score anomaly detection with type classification |
| get\_top\_metrics | JSONB array | Rank and return top N metrics by value |
| calculate\_cumulative\_trend | JSONB array | Cumulative trend with growth acceleration |
| classify\_trend | JSONB array | Classify trend as strong\_up/up/flat/down/strong\_down |
| calculate\_percent\_change\_comparison | JSONB array | A/B test % change with relative uplift |
| calculate\_absolute\_change\_comparison | JSONB array | A/B test absolute change with z-score significance |
| calculate\_prepost\_comparison | JSONB array | Pre/post entity-level change around an event cutoff |
| calculate\_stratified\_analysis | JSONB array | Stratum-adjusted effects (Mantel-Haenszel) |
| calculate\_bootstrap\_ci | JSONB array | Bootstrap CIs for mean/median/std — robust to non-normality |
| calculate\_power\_analysis | Scalar params | Required sample size for desired statistical power |
| calculate\_effect\_sizes | Two JSONB arrays | Cohen d, Hedges g, Glass delta with interpretation |
| adjust\_pvalues\_bonferroni | JSONB array | Multiple comparison correction to control FWER |
| calculate\_sequential\_analysis | JSONB array | A/B test early stopping with O'Brien-Fleming boundary |
| calculate\_cuped\_adjustment | JSONB arrays | CUPED variance reduction using pre-experiment covariates |
| calculate\_moving\_average | JSONB array | Unified SMA/WMA/EMA with deviation detection |

 