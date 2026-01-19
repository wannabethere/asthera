# Playbook: Cornerstone API → People/Training Assets → Time Series → SOC2/HIPAA/General Risk

This playbook defines **lane-based** agent workflows to ingest Cornerstone (CSOD) Learning/Transcript data, build canonical tables, generate **silver** features, and produce time series snapshots for **SOC2**, **HIPAA**, and **General** training compliance risk.

## Source references (Cornerstone developer portal)
- Authentication: OAuth2 client credentials (Cornerstone only supports client credentials)  
- Transcript APIs: access a user’s transcript; Transcript Search recommended for bulk  
- Learning Assignment APIs: create/search standard assignments  
(These concepts are documented on csod.dev: Authentication + Transcript + Learning Assignment guides.)

---

## Canonical model (recommended)
Treat **people and training obligations** as “assets” in your risk system.

- **Person asset**: one row per employee/contractor (your in-scope workforce)
- **Training obligation**: the policy requirement (e.g., HIPAA Privacy annually)
- **Training assignment / transcript record**: evidence of completion, due dates, status

### Minimal tables
**Bronze (raw)**
- `raw_csod_users`
- `raw_csod_transcripts`
- `raw_csod_assigned_trainings`
- `raw_csod_tasks` (optional)
- `raw_csod_assignments` (admin-created assignments; optional)

**Silver (canonical)**
- `hr_people_assets` (or reuse `dev_assets` with `device_type='person'`)
- `hr_training_obligations`
- `hr_training_instances` (one row per person × obligation × learning object)
- `hr_training_features_silver`
- `soc2_training_risk_timeseries`
- `hipaa_training_risk_timeseries`
- `general_training_risk_timeseries`

---

# Lane 0 — Bootstrap (Schema + Enum + Knowledge)
**Agent:** `KnowledgeBootstrapAgent`  
**Goal:** load enum metadata + obligation mappings and confirm schemas exist.

**Outputs**
- Enum metadata tables seeded (see `cornerstone_enum_metadata.sql`)
- Obligation catalog:
  - `framework` (SOC2/HIPAA/COMMON)
  - `obligation_code` (e.g., `hipaa_privacy`)
  - mapping rules (role tags, department, job family, access to ePHI, etc.)

---

# Lane 1 — Cornerstone Ingestion (Bronze)
**Agent:** `CornerstoneConnectorAgent`  
**Goal:** fetch transcript/assigned training signals for decision-making.

**Inputs**
- OAuth2 client credential config
- User population scope (active users)

**Steps**
1. Pull **users** (active)
2. Pull **transcripts** per user (or use transcript search for bulk)
3. Pull **assigned trainings** per user (status + due date)
4. Pull **tasks/approvals** if you want “workflow completeness” signals

**Outputs**
- Raw append-only tables with: `observed_at`, `source_system='cornerstone'`, `source_record_id`

---

# Lane 2 — Identity & Assetization (People Assets)
**Agent:** `PersonIdentityResolverAgent`  
**Goal:** build canonical “person assets”.

**Steps**
1. Create stable person key (e.g., `person_key = hash(externalId)`)
2. Populate `hr_people_assets` (or map into `dev_assets`):
   - name/email/externalId
   - org/department/role tags
   - employment status (active/terminated)
3. Assign scope:
   - `soc2_scope_state`
   - `hipaa_scope_state` (ePHI access proxy or role mapping)

---

# Lane 3 — Training Instance Normalization (Transcript → Canonical)
**Agent:** `TrainingInstanceNormalizerAgent`  
**Goal:** normalize transcript + assignment into a consistent record.

**Steps**
1. For each person, join:
   - transcript records (completion, status)
   - assigned trainings (due dates, assignment state)
2. Normalize into `hr_training_instances`:
   - `person_key`, `obligation_code`, `learning_object_id`
   - `training_status` (enum normalized)
   - `assigned_at`, `due_at`, `completed_at`
   - `is_past_due`, `days_past_due`, `days_to_due`
   - `source_refs` back to raw records

---

# Lane 4 — Silver Feature Compiler (Non-aggregate)
**Agent:** `TrainingFeatureCompilerAgent`  
**Goal:** compute per-person-per-obligation features (silver).

**Examples**
- `training_last_seen_ts` (freshness of transcript evidence)
- `training_status_normalized` (enum)
- `days_past_due`
- `days_to_due`
- `has_failed_attempt`
- `has_no_assignment_gap` (coverage gap)
- `training_obligation` (framework-scoped enum)

Outputs → `hr_training_features_silver`

---

# Lane 5 — Impact / Likelihood / Risk engines (SOC2/HIPAA/General)
**Agents:** `TrainingImpactAgent`, `TrainingLikelihoodAgent`, `TrainingRiskAgent`

**General**
- impact: obligation criticality + role + regulated scope
- likelihood: due proximity + past-due + not-started + failed attempt
- risk = impact × likelihood

**SOC2**
- weight higher for: security awareness, access control, change mgmt obligations

**HIPAA**
- weight higher for: privacy/security/incident training for ePHI workforce

Outputs:
- `general_raw_impact`, `general_raw_likelihood`, `general_raw_risk`
- `soc2_raw_impact`, `soc2_raw_likelihood`, `soc2_raw_risk`
- `hipaa_raw_impact`, `hipaa_raw_likelihood`, `hipaa_raw_risk`
- plus class labels (enums): `training_impact_class`, `training_likelihood_class`, `training_risk_level`
- `training_risk_driver_primary` (framework-scoped)

---

# Lane 6 — Time Series Snapshots
**Agent:** `TrainingTimeSeriesAgent`  
**Goal:** produce daily/hourly snapshots for dashboards + monitoring.

Output tables:
- `general_training_risk_timeseries`
- `soc2_training_risk_timeseries`
- `hipaa_training_risk_timeseries`

Snapshot fields:
- `snapshot_ts`
- `person_key`, `obligation_code`
- raw scores + class labels + driver
- key evidence fields (due date, completed_at, status)

---

# Lane 7 — Control Evaluation + Evidence Packaging
**Agent:** `ComplianceEvidenceAgent`  
**Goal:** translate features into control posture and export evidence packs.

Outputs:
- `hr_control_status` (per person × obligation × framework)
- `soc2_evidence_packages` / `hipaa_evidence_packages` (optional)

---

## Guardrails: “Silver-only” constraints
✅ OK:
- per-person-per-obligation derived features
- per-person status flags and days-to-due
- per-person risk scores (raw + enum labels)

⛔ Avoid (gold):
- org-wide completion rate
- average days past due across departments
- MTTR-style aggregates across population

---

## Acceptance tests (per lane)
- Lane 1: raw tables have `observed_at` and stable IDs
- Lane 2: every active person has a stable `person_key`
- Lane 3: training status is normalized to `training_status` enum
- Lane 5: risk scores produce valid enum labels (no missing codes)
- Lane 6: time series is append-only and monotonic per day
