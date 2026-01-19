-- =====================================================================================
-- Cornerstone (CSOD) Compliance / Training Enum Metadata (Postgres)
-- Purpose: Support silver-layer feature engineering + time-series scoring for
--          SOC2 / HIPAA / General training compliance using Cornerstone API data.
-- Notes:
--   * These tables complement your existing risk_impact_metadata, likelihood_vuln_attributes_metadata,
--     telemetry_freshness_metadata, risk_driver_metadata, etc.
--   * Keep enums stable; avoid embedding business rules here. Put rule logic in features/agents.
-- =====================================================================================

-- 1) Training / Transcript status normalization ----------------------------------------
CREATE TABLE IF NOT EXISTS public.training_status_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'training_status',
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, code)
);

INSERT INTO public.training_status_metadata (enum_type, code, display_name, description, sort_order)
VALUES
  ('training_status','assigned','Assigned','Training assigned to learner; not started.',10),
  ('training_status','in_progress','In progress','Learner has started but not completed.',20),
  ('training_status','completed','Completed','Training completed successfully.',30),
  ('training_status','failed','Failed','Training attempted but not passed/failed assessment.',40),
  ('training_status','past_due','Past due','Training due date has passed and is not completed.',50),
  ('training_status','waived','Waived','Training requirement waived by policy/role exception.',60),
  ('training_status','removed','Removed','Training removed/archived from transcript (may be not retrievable via API).',70),
  ('training_status','unknown','Unknown','Status could not be determined from source fields.',99)
ON CONFLICT (enum_type, code) DO NOTHING;

-- 2) Training obligation (framework-scoped) -------------------------------------------
CREATE TABLE IF NOT EXISTS public.training_obligation_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'training_obligation',
  framework        TEXT    NOT NULL DEFAULT 'COMMON', -- COMMON | SOC2 | HIPAA (extendable)
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, framework, code)
);

INSERT INTO public.training_obligation_metadata (enum_type, framework, code, display_name, description, sort_order)
VALUES
  ('training_obligation','COMMON','security_awareness','Security Awareness','General security awareness training obligation.',10),
  ('training_obligation','COMMON','privacy_awareness','Privacy Awareness','General privacy awareness training obligation.',20),
  ('training_obligation','COMMON','phishing','Phishing Training','Anti-phishing training obligation.',30),
  ('training_obligation','COMMON','incident_response','Incident Response','Incident response / reporting training obligation.',40),

  ('training_obligation','SOC2','soc2_security_awareness','SOC2 Security Awareness','SOC2-aligned security awareness obligation for employees/contractors.',10),
  ('training_obligation','SOC2','soc2_access_control','SOC2 Access Control','SOC2-aligned access control / acceptable use obligation.',20),
  ('training_obligation','SOC2','soc2_change_mgmt','SOC2 Change Management','SOC2-aligned change management / SDLC training obligation.',30),

  ('training_obligation','HIPAA','hipaa_privacy','HIPAA Privacy','HIPAA Privacy Rule training obligation for workforce members.',10),
  ('training_obligation','HIPAA','hipaa_security','HIPAA Security','HIPAA Security Rule training obligation for workforce members.',20),
  ('training_obligation','HIPAA','hipaa_incident','HIPAA Incident Reporting','HIPAA incident reporting / breach response training obligation.',30)
ON CONFLICT (enum_type, framework, code) DO NOTHING;

-- 3) Training criticality / impact class (training-only) -------------------------------
CREATE TABLE IF NOT EXISTS public.training_impact_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'training_impact_class',
  framework        TEXT    NOT NULL DEFAULT 'COMMON', -- COMMON | SOC2 | HIPAA
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  impact_score     NUMERIC(6,3),  -- optional calibration anchor
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, framework, code)
);

INSERT INTO public.training_impact_metadata (enum_type, framework, code, display_name, description, impact_score, sort_order)
VALUES
  ('training_impact_class','COMMON','low','Low','Low impact if overdue/non-compliant.',0.25,10),
  ('training_impact_class','COMMON','medium','Medium','Moderate impact if overdue/non-compliant.',0.50,20),
  ('training_impact_class','COMMON','high','High','High impact if overdue/non-compliant.',0.75,30),
  ('training_impact_class','COMMON','critical','Critical','Critical impact if overdue/non-compliant (regulatory / privileged roles).',1.00,40),

  ('training_impact_class','SOC2','high','High (SOC2)','High impact for SOC2 evidence readiness and security posture.',0.80,30),
  ('training_impact_class','SOC2','critical','Critical (SOC2)','Critical impact for SOC2 trust services criteria evidence.',1.00,40),

  ('training_impact_class','HIPAA','high','High (HIPAA)','High impact for HIPAA workforce compliance.',0.85,30),
  ('training_impact_class','HIPAA','critical','Critical (HIPAA)','Critical impact for HIPAA regulated workflows / ePHI access roles.',1.00,40)
ON CONFLICT (enum_type, framework, code) DO NOTHING;

-- 4) Training likelihood class (risk of non-completion / lateness) ---------------------
CREATE TABLE IF NOT EXISTS public.training_likelihood_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'training_likelihood_class',
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  likelihood_score NUMERIC(6,3),  -- optional calibration anchor
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, code)
);

INSERT INTO public.training_likelihood_metadata (enum_type, code, display_name, description, likelihood_score, sort_order)
VALUES
  ('training_likelihood_class','unlikely','Unlikely','Low risk of non-completion (on track).',0.20,10),
  ('training_likelihood_class','possible','Possible','Moderate risk of non-completion (watch).',0.45,20),
  ('training_likelihood_class','likely','Likely','High risk of non-completion (intervene).',0.70,30),
  ('training_likelihood_class','imminent','Imminent','Very high risk of non-completion/past-due.',0.90,40),
  ('training_likelihood_class','unknown','Unknown','Cannot estimate likelihood due to missing due/assignment signals.',0.50,99)
ON CONFLICT (enum_type, code) DO NOTHING;

-- 5) Training risk level (training-specific) ------------------------------------------
CREATE TABLE IF NOT EXISTS public.training_risk_level_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'training_risk_level',
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  min_score        NUMERIC(8,3),
  max_score        NUMERIC(8,3),
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, code)
);

INSERT INTO public.training_risk_level_metadata (enum_type, code, display_name, description, min_score, max_score, sort_order)
VALUES
  ('training_risk_level','low','Low','Low training non-compliance risk.',0.00,0.30,10),
  ('training_risk_level','medium','Medium','Moderate training non-compliance risk.',0.30,0.60,20),
  ('training_risk_level','high','High','High training non-compliance risk.',0.60,0.85,30),
  ('training_risk_level','critical','Critical','Critical training non-compliance risk.',0.85,1.01,40),
  ('training_risk_level','unknown','Unknown','Risk cannot be computed reliably.',NULL,NULL,99)
ON CONFLICT (enum_type, code) DO NOTHING;

-- 6) Training risk drivers (shared enum type + framework) ------------------------------
CREATE TABLE IF NOT EXISTS public.training_risk_driver_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'training_risk_driver_primary',
  framework        TEXT    NOT NULL DEFAULT 'COMMON', -- COMMON | SOC2 | HIPAA
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  category_hint    TEXT,
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, framework, code)
);

INSERT INTO public.training_risk_driver_metadata (enum_type, framework, code, display_name, description, category_hint, sort_order)
VALUES
  ('training_risk_driver_primary','COMMON','past_due','Past due','Training due date passed without completion.', 'likelihood',10),
  ('training_risk_driver_primary','COMMON','due_soon','Due soon','Training is due soon and not completed.', 'likelihood',20),
  ('training_risk_driver_primary','COMMON','not_started','Not started','Training assigned but not started.', 'likelihood',30),
  ('training_risk_driver_primary','COMMON','failed_attempt','Failed attempt','Learner attempted but failed/pending success.', 'likelihood',40),
  ('training_risk_driver_primary','COMMON','missing_assignment','Missing assignment','Obligation exists but training not assigned (coverage gap).', 'control',50),
  ('training_risk_driver_primary','COMMON','scope_unknown','Scope unknown','Role/regulatory scope could not be determined.', 'scope',60),
  ('training_risk_driver_primary','COMMON','unknown','Unknown','Driver not classified; needs mapping rules.', 'unknown',99),

  ('training_risk_driver_primary','SOC2','soc2_security_awareness_gap','SOC2 Security Awareness gap','Security awareness training not completed for SOC2 in-scope roles.', 'control',10),
  ('training_risk_driver_primary','SOC2','soc2_change_mgmt_gap','SOC2 Change Mgmt gap','Change management training not completed for engineering roles.', 'control',20),

  ('training_risk_driver_primary','HIPAA','hipaa_privacy_gap','HIPAA Privacy gap','HIPAA privacy training missing/overdue for ePHI workforce.', 'control',10),
  ('training_risk_driver_primary','HIPAA','hipaa_security_gap','HIPAA Security gap','HIPAA security training missing/overdue for ePHI workforce.', 'control',20)
ON CONFLICT (enum_type, framework, code) DO NOTHING;
