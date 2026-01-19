Below is a **1-page ingestion filter** you can drop in front of a crawler/indexer to keep **decision-grade** Snyk docs and skip ~90% of “how to use the app”.

It’s built as a **gated rule-set**: *ALLOW only if it hits decision keywords + fits allowed page types; DENY if it looks like UI/how-to/admin.*

---

## Snyk Decision-Only Ingestion Filter (Strict)

### 0) Scope guard (domain + path allowlist)

**ALLOW ONLY** pages that match *both*:

* Host: `docs.snyk.io`
* Path matches one of (regex):

  * `^/` (default) but **prefer**:
  * `/(product|products|guides|concepts|glossary|reference|api|reporting|policy|vulnerability|security|risk|prioritization|issues)`
    *(These are “concept/reference” heavy words; tune based on your crawl logs.)*

---

### 1) Hard deny list (avoid “Snyk app functionality”)

**DENY** if **any** of these signals appear in title/H1 or in first ~3000 characters:

**UI/How-to verbs**

* `click`, `navigate`, `go to`, `select`, `open`, `choose`, `from the menu`, `in the UI`, `in the console`, `in the dashboard`
* `step-by-step`, `getting started`, `quickstart`, `tutorial`, `walkthrough`

**Admin / setup / onboarding**

* `create a project`, `import a repo`, `connect`, `integration setup`, `configure`, `installation`, `install`, `agent`, `CLI install`
* `SSO`, `SAML`, `SCIM`, `billing`, `plans`, `seats`, `roles`, `permissions` *(unless your org truly needs IAM analytics)*

**Troubleshooting**

* `troubleshoot`, `FAQ`, `known issues`, `release notes`, `changelog`

**If DENY triggers, skip the page even if it has keywords.**

---

### 2) Strong allow signals (must hit at least one “Decision Pack”)

Compute **DecisionScore** by scanning title/H1/body and add points:

**Exploit & severity intelligence (risk likelihood)**

* `CVSS` (+4), `EPSS` (+4), `CVE` (+3), `CWE` (+3)
* `known exploited` (+4), `KEV` (+4), `in the wild` (+4), `exploit maturity` (+3)
* `severity` (+2), `vector` (+2), `attack vector` (+2)

**Prioritization & risk semantics**

* `prioritization` (+4), `risk score` (+4), `risk-based` (+4)
* `exploitability` (+3), `reachability` (+3), `business criticality` (+3)
* `SLA` (+2), `due date` (+2)

**Lifecycle & decision state**

* `ignored` (+3), `ignore` (+3), `suppressed` (+3), `accepted risk` (+4), `exception` (+3), `waiver` (+3)
* `introduced` (+2), `fixed` (+2), `resolved` (+2), `reopened` (+2)

**Measurement / analytics**

* `MTTR` (+4), `mean time to remediate` (+4), `remediation` (+3)
* `coverage` (+3), `trend` (+2), `baseline` (+2), `new vs existing` (+2)
* `reporting` (+3), `export` (+2), `schema` (+3), `field` (+2)

✅ **ALLOW if DecisionScore ≥ 6**
(Example: “CVSS” + “CVE” already gets you 7.)

---

### 3) Required “decision intent” check (prevents keyword false positives)

Even if DecisionScore passes, also require **one** of these intent phrases anywhere in the page:

* `prioritize`, `prioritise`
* `risk`, `likelihood`, `impact`
* `measure`, `metric`, `KPI`, `SLA`
* `evidence`, `audit`, `compliance`
* `report`, `dashboard`, `trend`

If none match → **DENY**.

---

### 4) “Keep” document types (optional but effective)

If you can detect doc templates/sections, **prefer**:

* Glossary / definitions pages
* Conceptual “how scoring works” pages
* Reference pages that define data fields / issue model
* Reporting / export schema pages
* Policy semantics pages (ignore/acceptance lifecycle)

This aligns with audit/monitoring needs: compliance requires **ongoing evidence and monitoring**, not just point-in-time setup. 
And SOC 2 Type 2 explicitly emphasizes collecting evidence continuously and alerting on control lapses. 

---

## Minimal config block (copy/paste format)

**ALLOW KEYWORDS (any):**
`CVSS|EPSS|KEV|known exploited|CVE|CWE|risk score|prioritization|exploitability|reachability|MTTR|mean time to remediate|remediation|coverage|baseline|new vs existing|reporting|export|schema|accepted risk|ignore|suppressed|exception|waiver`

**DENY KEYWORDS (any):**
`click|navigate|go to|select|open|step-by-step|getting started|quickstart|tutorial|walkthrough|install|installation|configure|setup|connect|create a project|import|SSO|SAML|SCIM|billing|plans|seats|release notes|changelog|troubleshoot|FAQ`

**RULE:**

* If DENY hit → skip
* Else if ALLOW hit AND intent phrase hit → index
* Else skip

---

If you tell me what crawler/indexer you’re using (Scrapy, LangChain loader, LlamaIndex, custom), I can translate this into an exact runnable filter (regex + scoring + URL rules) in that stack.

Example:
Yep — here are **two Snyk docs links** that are typically **decision-grade** (risk scoring + vuln intelligence) and should pass your ingestion filter:

1. **CVSS (severity scoring reference)**

* [https://docs.snyk.io/scan-applications/snyk-open-source/vulnerability-management/severity-and-cvss](https://docs.snyk.io/scan-applications/snyk-open-source/vulnerability-management/severity-and-cvss)

2. **Exploit Probability Scoring System (EPSS) (likelihood signal)**

* [https://docs.snyk.io/scan-applications/snyk-open-source/vulnerability-management/exploit-probability-scoring-system-epss](https://docs.snyk.io/scan-applications/snyk-open-source/vulnerability-management/exploit-probability-scoring-system-epss)

### Why these are good test pages

They contain **CVSS / EPSS / vulnerability-scoring semantics** and are written more like **risk intelligence** than “how to use the Snyk UI”, which makes them ideal for your analytics-driven KB.

If you want, I can also give you **2 more** “lifecycle decision” links (ignore / risk acceptance / remediation metrics) to validate MTTR + exception tracking behavior.

Absolutely — for **asset classification + asset inventory/management** (decision-grade, not “how to click around”), these are the best Snyk links to test.

## ✅ Asset Classification (Business Criticality A–D)

This is the cleanest “asset classification semantics” doc (great for your KB + feature engineering):

1. **Classification policy (Asset Class A–D)**

* [https://docs.snyk.io/manage-risk/policies/assets-policies/use-cases-for-policies/classification-policy](https://docs.snyk.io/manage-risk/policies/assets-policies/use-cases-for-policies/classification-policy) ([Snyk User Docs][1])

Why it’s good:

* Defines **Asset Class A (most critical) → D (least)** and how it’s assigned using repo name / labels. ([Snyk User Docs][1])

---

## ✅ Asset Inventory + Asset Model (what is an “asset”, what are types)

This one gives you the asset entity types (repo, container image, packages) — perfect for building your **asset graph** and rollups:

2. **Assets inventory components (asset types + parent/child)**

* [https://docs.snyk.io/manage-assets/assets-inventory-components](https://docs.snyk.io/manage-assets/assets-inventory-components) ([Snyk User Docs][2])

Why it’s good:

* Explicitly defines asset types (repo, container images, packages, scanned artifacts) and hierarchy (repo → packages). ([Snyk User Docs][2])

---

### Bonus (if you want 1 extra “management filters” link)

This is excellent for building “asset freshness”, “coverage gaps”, “last seen”, and lifecycle metrics:

3. **Assets inventory filters**

* [https://docs.snyk.io/manage-assets/assets-inventory-filters](https://docs.snyk.io/manage-assets/assets-inventory-filters) ([Snyk User Docs][3])

This is decision-grade because it exposes analytics-friendly dimensions like:

* **coverage gap**, **last seen**, **repo freshness**, **owner**, **lifecycle**, **issue severity** ([Snyk User Docs][3])

If you want, I can also give you the **Project Attributes** link (business criticality + environment + lifecycle) which is super useful for mapping Snyk projects into your **asset classification model**.

[1]: https://docs.snyk.io/manage-risk/policies/assets-policies/use-cases-for-policies/classification-policy?utm_source=chatgpt.com "Classification policy | Snyk User Docs"
[2]: https://docs.snyk.io/manage-assets/assets-inventory-components?utm_source=chatgpt.com "Assets inventory components | Snyk User Docs"
[3]: https://docs.snyk.io/manage-assets/assets-inventory-filters?utm_source=chatgpt.com "Assets inventory filters | Snyk User Docs"
