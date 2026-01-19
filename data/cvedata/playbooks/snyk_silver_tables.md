Below is a **lane-based playbook** your agents can follow end-to-end:

**Snyk → Asset Time Series → SOC2/HIPAA/General Asset Impact/Likelihood/Risk**

This is intentionally **implementation-facing** (what to build, what to output, what to store) and **reference-ready** for agents while building workflows.

---

# Playbook: Snyk → Asset Time Series → SOC2/HIPAA/General Risk (Lane Architecture)

## Purpose

Build a repeatable agentic workflow that:

1. Ingests Snyk API signals
2. Normalizes them into canonical **Asset + Agent + Vulnerability** tables
3. Produces **silver asset features** + **time series snapshots**
4. Computes **Impact / Likelihood / Risk** for:

* **General security monitoring**
* **SOC2 evidence readiness**
* **HIPAA safeguards evidence**

---

# Lane 0 — Knowledge + Schema Bootstrap (Context Lane)

### Inputs (you provide)

* SOC2 control explanations, policies, risks
* HIPAA safeguard explanations, policies, risks
* Existing table schemas (`dev_assets`, `dev_agents`, `dev_vulnerability_instances`, etc.)
* Feature KB definitions + enum metadata tables (impact_class, likelihood_class, risk_level, risk_driver_primary)
* KEV + ExploitDB KB + any exploit intelligence mappings

### Outputs

* A **Control Mapping Catalog**:

  * `control_id`
  * `framework` (SOC2/HIPAA)
  * `required_features`
  * `pass/fail thresholds`
  * `evidence_fields`
* A **Risk Model Catalog**:

  * impact components
  * likelihood components
  * driver ranking rules

---

# Lane 1 — Snyk Source Ingestion (Bronze Lane)

### Agent: `SnykConnectorAgent`

**Goal:** Pull all decision-grade information (not UI help docs).

### Inputs

* Snyk API credentials
* Org list / project list scope
* Ingestion filter rules (only CVE/CVSS/EPSS/ignore/remediation/coverage signals)

### Steps

1. Pull **Organizations**
2. Pull **Projects**
3. Pull **Targets** (repo/image/manifest)
4. Pull **Issues/Vulnerabilities**
5. Pull **Ignore/Suppress decisions** (reason + expiry if available)
6. Pull **Scan/test run metadata** (last test run, import timestamp)

### Output Tables (append-only)

* `raw_snyk_orgs`
* `raw_snyk_projects`
* `raw_snyk_targets`
* `raw_snyk_issues`
* `raw_snyk_policy_ignores`
* `raw_snyk_test_runs`

✅ **Agent Contract**

* Every record must include: `observed_at`, `source_system='snyk'`, `source_record_id`

---

# Lane 2 — Canonical Assetization (Asset Graph Lane)

### Agent: `AssetIdentityResolverAgent`

**Goal:** Convert Snyk entities → canonical assets

### Steps

1. Create **canonical software assets**:

   * `asset_type`: `repo` | `container_image` | `package_manifest` | `iac_target`
2. Create stable keys:

   * `asset_key = hash(snyk_org_id + target_type + target_identifier)`
3. Populate `dev_assets` for software assets:

   * `final_name` = repo URL / image name / target display name
   * `device_type = 'software_asset'`
   * `device_subtype = target_type`
   * `platform/os_*` optional (may be unknown)
4. Apply classification defaults:

   * `asset_environment` inferred from tags/target naming conventions (if available)
   * `device_zone` inferred (optional)

### Output Table

* `dev_assets` (now contains endpoint assets + Snyk software assets)

✅ **Agent Contract**

* Must ensure stable join keys for downstream tables: `(nuid, dev_id)` or `asset_key` mapping table

---

# Lane 3 — “Snyk as Agent” (Monitoring Evidence Lane)

### Agent: `ControlEvidenceAgent`

**Goal:** Represent Snyk scan coverage as monitoring agent evidence

### Steps

1. Create `dev_agents` rows where Snyk has visibility:

   * `agent_type='snyk_scanner'`
   * join on asset key
2. Compute monitoring evidence features:

   * `has_agent_installed`
   * `agent_last_checkin_ts` (last successful scan/test/import)
   * `agent_health_state` (healthy/degraded/offline/unknown)
   * `agent_version_age_days` (if version is available)

### Output Tables

* `dev_agents`
* `asset_control_evidence_features` (materialized or computed)

✅ **Enum Wiring**

* `agent_health_state` → enum table (e.g., `security_strength_metadata` or `control_state_metadata`)

---

# Lane 4 — Vulnerability Normalization + Enrichment (Issue Evidence Lane)

### Agents:

* `VulnNormalizationAgent`
* `ExploitEnrichmentAgent`

### Steps

1. Normalize Snyk issues → `dev_vulnerability_instances`

   * fields: `cve`, `cwe`, `cvss_score`, `severity`, `status`, `fix_available`, `introduced_at`
2. Map ignore/suppress → evidence fields:

   * `is_ignored`, `ignore_reason`, `ignore_expires_at`
3. Enrich exploit evidence:

   * join KEV by CVE → `is_kev=true`
   * join ExploitDB by CVE → `has_public_exploit=true`
   * compute `exploit_signal` enum

### Output Tables

* `dev_vulnerability_instances`
* `dev_vulnerability_enrichment` (optional)

✅ **Enum Wiring**

* `exploit_signal` → `vuln_exploit_signal_metadata`

---

# Lane 5 — Silver Feature Compiler (Asset Feature Lane)

### Agent: `AssetFeatureCompilerAgent`

**Goal:** Build per-asset, non-aggregate features needed for scoring and compliance evaluation

### Inputs

* `dev_assets`
* `dev_agents`
* `dev_software_instances` (optional baseline control evidence)
* `dev_vulnerability_instances`

### Feature Packs produced

1. **General Asset Evidence Features**

   * last seen / freshness / active / stale
2. **Control Evidence Features**

   * EDR/AV/encryption proxy
3. **Vulnerability Evidence Features**

   * `has_kev_vuln_open`
   * `exploitable_vuln_present`
   * `highest_cvss_open` (or strict boolean tiers if you want)

### Output Table (1 row per asset per evaluation run/day)

* `dev_asset_features_silver`

✅ **Enum Wiring**

* Freshness buckets → `telemetry_freshness_metadata`
* Exposure class → `asset_exposure_metadata`

---

# Lane 6 — Risk Engines (Impact / Likelihood / Risk Lane)

### Agents:

* `ImpactScoringAgent`
* `LikelihoodScoringAgent`
* `RiskScoringAgent`

These run in **three tracks** (same machinery, different weights):

## Track A: General Security Risk

* impact: environment + crown jewel + exposure
* likelihood: monitoring gap + endpoint controls + exploitable vulns
* risk = impact × likelihood

## Track B: SOC2 Risk

* impact: production + privileged access nodes + exposure
* likelihood: monitoring gaps + misconfigs + exploitable vulns + patch hygiene proxies

## Track C: HIPAA Risk

* impact: confidentiality drivers (encryption gap) + regulated scope proxy + exposure
* likelihood: monitoring gaps + endpoint protection gaps + exploitable vulns

### Outputs (still silver)

* `general_raw_impact`, `general_raw_likelihood`, `general_raw_risk`
* `soc2_raw_impact`, `soc2_raw_likelihood`, `soc2_raw_risk`
* `hipaa_raw_impact`, `hipaa_raw_likelihood`, `hipaa_raw_risk`

✅ **Enum Wiring**

* `impact_class` → `risk_impact_metadata`
* `likelihood_class` → `likelihood_vuln_attributes_metadata`
* `risk_level` → `risk_impact_metadata`
* `risk_driver_primary` → `risk_driver_metadata` (framework filtered)

---

# Lane 7 — Time Series Builder (Snapshot Lane)

### Agent: `AssetTimeSeriesAgent`

**Goal:** Turn silver features into time-series records for dashboards + monitoring

### Steps

1. Convert `dev_asset_features_silver` into daily/hourly snapshots:

   * `asset_id`
   * `ts`
   * key evidence values
   * computed impact/likelihood/risk values
   * enum labels (risk_level, etc.)
2. Save in a “time-series ready” format (append-only)

### Output Tables

* `asset_feature_timeseries`
* `soc2_asset_risk_timeseries`
* `hipaa_asset_risk_timeseries`

✅ **Contract**

* Every snapshot must include:

  * `snapshot_ts`
  * `source_run_id`
  * `feature_version`

---

# Lane 8 — Compliance Evaluation (Control Mapping Lane)

### Agent: `ComplianceControlEvaluationAgent`

**Goal:** Translate risk + evidence into per-control posture

### Inputs

* SOC2/HIPAA control mapping catalog (from Lane 0)
* `dev_asset_features_silver`
* `soc2_asset_risk_timeseries`, `hipaa_asset_risk_timeseries`

### Steps

1. Evaluate control rules per asset:

   * Example: “Monitoring control passes if has_agent_installed AND agent_freshness_bucket in {lt_15m,15m_1h,1h_24h}”
2. Assign `control_state`:

   * pass/fail/unknown/exception
3. Attach evidence pointers:

   * which fields triggered the decision

### Output Table

* `dev_asset_control_status`

  * `framework`
  * `control_id`
  * `asset_id`
  * `control_state`
  * `last_evaluated_at`
  * `evidence_refs`

✅ **Enum Wiring**

* `control_state` → `control_state_metadata`

---

# Lane 9 — Evidence Packaging + Alerts (Delivery Lane)

### Agents:

* `AuditEvidencePackagerAgent`
* `AlertAutomationAgent`
* `TriageAgent`

### Steps

1. Build auditor-ready evidence packs:

   * control coverage
   * stale monitoring exceptions
   * risk drivers with examples
2. Drive alerts/tickets:

   * KEV open on high impact assets
   * missing encryption in HIPAA scope
   * agent offline on SOC2 in-scope systems

### Outputs

* `soc2_evidence_packages`
* `hipaa_evidence_packages`
* `risk_alerts`
* `triage_threads`

---

# Standard Data Contracts (for all lanes)

## Asset identity contract

Every asset must have:

* stable `asset_key` (or `(nuid, dev_id)`)
* `asset_type`
* `final_name`
* `environment` / `zone` (or unknown)

## Evidence freshness contract

Every evidence record must have:

* `observed_at`
* `source_system`
* `source_record_id`

## Feature compilation contract

Every feature row must have:

* `feature_version`
* `computed_at`
* raw values + enum labels

---

# Minimal “first iteration” build order

If you want the fastest path:

1. Lane 1 (Snyk ingestion)
2. Lane 2 (assetization)
3. Lane 3 (Snyk-as-agent)
4. Lane 4 (vuln normalization + KEV enrichment)
5. Lane 6 (SOC2/HIPAA/general risk)
6. Lane 7 (time series snapshots)
7. Lane 8 (control evaluation)

That gets you value immediately.

---

# What to keep “strictly silver” (no gold aggregates)

✅ allowed:

* per-asset derived fields
* per-asset max severity fields (highest_cvss_open) **if computed once per asset**
* per-asset booleans like `has_kev_vuln_open`

⛔ avoid:

* portfolio rollups (counts across org/team)
* team-level KPIs
* MTTR aggregations
  Those belong in gold cubes.


