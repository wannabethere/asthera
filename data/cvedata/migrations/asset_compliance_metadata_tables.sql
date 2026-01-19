-- =====================================================================================
-- Enum Metadata Tables (Postgres) for SOC2/HIPAA Asset Control + Risk Modeling
-- - Strict enum PK pattern: (enum_type, control_type, code)
--   * control_type: 'SOC2' | 'HIPAA' | 'COMMON' (framework-neutral)
--   * Exception: telemetry_freshness_metadata uses (enum_type, code) since buckets apply across frameworks
-- - All tables live in: public
-- - Notes:
--   * Keep these "decision enums" stable; do NOT bake business logic into the enum tables.
--   * Use min/max fields as optional calibration anchors for your transform layer.
--   * Use control_type='COMMON' for framework-neutral entries; 'SOC2'/'HIPAA' for framework-specific.
-- =====================================================================================

-- 1) CONTROL STATE ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.control_state_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'control_state',
  control_type     TEXT    NOT NULL DEFAULT 'COMMON',  -- 'SOC2' | 'HIPAA' | 'COMMON'
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, control_type, code)
);

-- Add control_type column if table already exists (idempotent migration)
ALTER TABLE public.control_state_metadata
  ADD COLUMN IF NOT EXISTS control_type TEXT NOT NULL DEFAULT 'COMMON';

-- Replace PK to include control_type (idempotent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public' AND table_name = 'control_state_metadata'
    AND constraint_type = 'PRIMARY KEY'
    AND constraint_name = 'control_state_metadata_pkey'
  ) THEN
    -- Check if PK already includes control_type by counting columns
    IF (SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'control_state_metadata'
        AND constraint_name = 'control_state_metadata_pkey') < 3 THEN
      EXECUTE 'ALTER TABLE public.control_state_metadata DROP CONSTRAINT control_state_metadata_pkey';
      EXECUTE 'ALTER TABLE public.control_state_metadata ADD CONSTRAINT control_state_metadata_pkey PRIMARY KEY (enum_type, control_type, code)';
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_control_state_metadata_control_type
  ON public.control_state_metadata (control_type, enum_type);

INSERT INTO public.control_state_metadata (enum_type, control_type, code, display_name, description, sort_order)
VALUES
  ('control_state','COMMON','pass','Pass','Control evidence indicates the control is operating as expected.',10),
  ('control_state','COMMON','fail','Fail','Control evidence indicates the control is not operating / missing.',20),
  ('control_state','COMMON','unknown','Unknown','Insufficient telemetry to evaluate the control state.',30),
  ('control_state','COMMON','not_applicable','Not applicable','Control does not apply to this asset (by design/scope).',40),
  ('control_state','COMMON','exception_approved','Exception approved','Control is failing but has an approved exception / risk acceptance.',50),
  ('control_state','COMMON','exception_expired','Exception expired','Control exception existed but is now expired.',60)
ON CONFLICT (enum_type, control_type, code) DO NOTHING;


-- 2) TELEMETRY FRESHNESS ----------------------------------------------------
CREATE TABLE IF NOT EXISTS public.telemetry_freshness_metadata (
  enum_type        TEXT    NOT NULL,              -- e.g. 'freshness_bucket'
  code             TEXT    NOT NULL,              -- e.g. '<15m'
  display_name     TEXT    NOT NULL,
  description      TEXT,
  min_minutes      INT,                           -- inclusive lower bound (optional)
  max_minutes      INT,                           -- exclusive upper bound (optional)
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, code)
);

INSERT INTO public.telemetry_freshness_metadata
(enum_type, code, display_name, description, min_minutes, max_minutes, sort_order)
VALUES
  ('freshness_bucket','lt_15m','< 15 minutes','Near-real-time telemetry.',0,15,10),
  ('freshness_bucket','15m_1h','15 minutes – 1 hour','Recent telemetry; acceptable for many continuous controls.',15,60,20),
  ('freshness_bucket','1h_24h','1 hour – 24 hours','Daily telemetry; some controls may treat as borderline.',60,1440,30),
  ('freshness_bucket','1d_7d','1 day – 7 days','Stale; likely breaks continuous monitoring evidence.',1440,10080,40),
  ('freshness_bucket','gt_7d','> 7 days','Very stale; treat as monitoring gap until refreshed.',10080,NULL,50),

  -- Optional policy tiers (if you want standardized “what is stale” by framework/team)
  ('staleness_policy','strict','Strict','Stale if > 24h for critical assets; tighter evidence expectations.',NULL,NULL,10),
  ('staleness_policy','standard','Standard','Stale if > 7d; typical default for broad coverage.',NULL,NULL,20),
  ('staleness_policy','lenient','Lenient','Stale if > 30d; only for low-criticality or offline devices.',NULL,NULL,30)
ON CONFLICT (enum_type, code) DO NOTHING;


-- 3) ASSET SCOPE (SOC2/HIPAA) ----------------------------------------------
CREATE TABLE IF NOT EXISTS public.asset_scope_metadata (
  enum_type        TEXT    NOT NULL,              -- 'soc2_scope' | 'hipaa_scope' | 'scope_reason'
  control_type     TEXT    NOT NULL DEFAULT 'COMMON',  -- 'SOC2' | 'HIPAA' | 'COMMON'
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, control_type, code)
);

-- Add control_type column if table already exists (idempotent migration)
ALTER TABLE public.asset_scope_metadata
  ADD COLUMN IF NOT EXISTS control_type TEXT NOT NULL DEFAULT 'COMMON';

-- Replace PK to include control_type (idempotent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public' AND table_name = 'asset_scope_metadata'
    AND constraint_type = 'PRIMARY KEY'
    AND constraint_name = 'asset_scope_metadata_pkey'
  ) THEN
    IF (SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'asset_scope_metadata'
        AND constraint_name = 'asset_scope_metadata_pkey') < 3 THEN
      EXECUTE 'ALTER TABLE public.asset_scope_metadata DROP CONSTRAINT asset_scope_metadata_pkey';
      EXECUTE 'ALTER TABLE public.asset_scope_metadata ADD CONSTRAINT asset_scope_metadata_pkey PRIMARY KEY (enum_type, control_type, code)';
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_asset_scope_metadata_control_type
  ON public.asset_scope_metadata (control_type, enum_type);

INSERT INTO public.asset_scope_metadata (enum_type, control_type, code, display_name, description, sort_order)
VALUES
  ('soc2_scope','SOC2','in_scope','In scope','Asset is in scope for SOC 2 system boundary / evidence collection.',10),
  ('soc2_scope','SOC2','out_of_scope','Out of scope','Asset excluded from SOC 2 system boundary by definition.',20),
  ('soc2_scope','SOC2','unknown','Unknown','Scope not determined; missing tags/ownership or classification.',30),

  ('hipaa_scope','HIPAA','ephi_in_scope','ePHI in scope','Asset stores/processes/transmits ePHI or supports regulated workflows.',10),
  ('hipaa_scope','HIPAA','ephi_out_of_scope','ePHI out of scope','Asset does not handle ePHI and is excluded by policy.',20),
  ('hipaa_scope','HIPAA','unknown','Unknown','HIPAA scope unknown; requires dataflow mapping / ownership confirmation.',30),

  ('scope_reason','COMMON','prod_env','Production environment','Production systems are typically in scope for assurance.',10),
  ('scope_reason','COMMON','tagged_regulated','Tagged regulated','Asset explicitly tagged as regulated/crown-jewel.',20),
  ('scope_reason','COMMON','crown_jewel','Crown jewel','High-value system with elevated impact; must be tracked.',30),
  ('scope_reason','COMMON','bastion','Bastion / PAW','Privileged access point; higher evidence expectations.',40),
  ('scope_reason','COMMON','unknown_owner','Unknown owner','Ownership unknown; cannot reliably scope or assign controls.',90)
ON CONFLICT (enum_type, control_type, code) DO NOTHING;


-- 4) ASSET EXPOSURE ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.asset_exposure_metadata (
  enum_type        TEXT    NOT NULL,              -- 'exposure_class' | 'network_zone_class'
  control_type     TEXT    NOT NULL DEFAULT 'COMMON',  -- 'SOC2' | 'HIPAA' | 'COMMON'
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  impact_modifier  NUMERIC(6,3),                  -- optional calibration hint (e.g., multiply impact)
  likelihood_modifier NUMERIC(6,3),               -- optional calibration hint (e.g., multiply likelihood)
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, control_type, code)
);

-- Add control_type column if table already exists (idempotent migration)
ALTER TABLE public.asset_exposure_metadata
  ADD COLUMN IF NOT EXISTS control_type TEXT NOT NULL DEFAULT 'COMMON';

-- Replace PK to include control_type (idempotent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public' AND table_name = 'asset_exposure_metadata'
    AND constraint_type = 'PRIMARY KEY'
    AND constraint_name = 'asset_exposure_metadata_pkey'
  ) THEN
    IF (SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'asset_exposure_metadata'
        AND constraint_name = 'asset_exposure_metadata_pkey') < 3 THEN
      EXECUTE 'ALTER TABLE public.asset_exposure_metadata DROP CONSTRAINT asset_exposure_metadata_pkey';
      EXECUTE 'ALTER TABLE public.asset_exposure_metadata ADD CONSTRAINT asset_exposure_metadata_pkey PRIMARY KEY (enum_type, control_type, code)';
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_asset_exposure_metadata_control_type
  ON public.asset_exposure_metadata (control_type, enum_type);

INSERT INTO public.asset_exposure_metadata
(enum_type, control_type, code, display_name, description, impact_modifier, likelihood_modifier, sort_order)
VALUES
  ('exposure_class','COMMON','internet_exposed','Internet exposed','Directly reachable from the internet or externally routable.',1.200,1.400,10),
  ('exposure_class','COMMON','dmz','DMZ','Perimeter segment; semi-exposed systems.',1.150,1.250,20),
  ('exposure_class','COMMON','corp','Corporate','Internal corporate network segment.',1.000,1.000,30),
  ('exposure_class','COMMON','restricted','Restricted','Highly segmented zone (e.g., regulated enclaves).',1.050,0.850,40),
  ('exposure_class','COMMON','unknown','Unknown','Exposure cannot be determined from tags/zone.',1.050,1.050,90),

  ('network_zone_class','COMMON','prod','Production','Production environment zone.',1.200,1.100,10),
  ('network_zone_class','COMMON','nonprod','Non-production','Dev/test/staging.',0.800,0.950,20),
  ('network_zone_class','COMMON','corp','Corporate','Employee/corp endpoints.',1.000,1.000,30),
  ('network_zone_class','COMMON','edge','Edge','Edge/perimeter assets and appliances.',1.100,1.200,40),
  ('network_zone_class','COMMON','unknown','Unknown','Zone not normalized.',1.000,1.000,90)
ON CONFLICT (enum_type, control_type, code) DO NOTHING;


-- 5) ENDPOINT CONTROL STRENGTH ---------------------------------------------
CREATE TABLE IF NOT EXISTS public.endpoint_control_metadata (
  enum_type        TEXT    NOT NULL,              -- 'edr_strength'|'av_strength'|'encryption_strength'
  control_type     TEXT    NOT NULL DEFAULT 'COMMON',  -- 'SOC2' | 'HIPAA' | 'COMMON'
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  strength_score   NUMERIC(6,3),                  -- optional: 0..1 or 0..100
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, control_type, code)
);

-- Add control_type column if table already exists (idempotent migration)
ALTER TABLE public.endpoint_control_metadata
  ADD COLUMN IF NOT EXISTS control_type TEXT NOT NULL DEFAULT 'COMMON';

-- Replace PK to include control_type (idempotent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public' AND table_name = 'endpoint_control_metadata'
    AND constraint_type = 'PRIMARY KEY'
    AND constraint_name = 'endpoint_control_metadata_pkey'
  ) THEN
    IF (SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'endpoint_control_metadata'
        AND constraint_name = 'endpoint_control_metadata_pkey') < 3 THEN
      EXECUTE 'ALTER TABLE public.endpoint_control_metadata DROP CONSTRAINT endpoint_control_metadata_pkey';
      EXECUTE 'ALTER TABLE public.endpoint_control_metadata ADD CONSTRAINT endpoint_control_metadata_pkey PRIMARY KEY (enum_type, control_type, code)';
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_endpoint_control_metadata_control_type
  ON public.endpoint_control_metadata (control_type, enum_type);

INSERT INTO public.endpoint_control_metadata
(enum_type, control_type, code, display_name, description, strength_score, sort_order)
VALUES
  -- EDR
  ('edr_strength','COMMON','strong','Strong','EDR present + healthy + recent check-in.',0.95,10),
  ('edr_strength','COMMON','adequate','Adequate','EDR present but minor gaps (e.g., older version).',0.75,20),
  ('edr_strength','COMMON','weak','Weak','EDR present but unhealthy/stale telemetry.',0.40,30),
  ('edr_strength','COMMON','missing','Missing','No EDR detected.',0.00,40),
  ('edr_strength','COMMON','unknown','Unknown','Cannot determine EDR presence/health.',0.50,90),

  -- AV
  ('av_strength','COMMON','strong','Strong','AV present and enabled with active definitions.',0.90,10),
  ('av_strength','COMMON','adequate','Adequate','AV present but not consistently healthy.',0.70,20),
  ('av_strength','COMMON','weak','Weak','AV present but outdated/disabled signals.',0.35,30),
  ('av_strength','COMMON','missing','Missing','No AV detected.',0.00,40),
  ('av_strength','COMMON','unknown','Unknown','Cannot determine AV posture.',0.50,90),

  -- Encryption
  ('encryption_strength','COMMON','full_disk','Full disk','Full disk encryption enabled (primary compliance expectation).',0.95,10),
  ('encryption_strength','COMMON','partial','Partial','Some encryption present but not full-disk / not enforced.',0.60,20),
  ('encryption_strength','COMMON','missing','Missing','Disk encryption not detected.',0.00,30),
  ('encryption_strength','COMMON','unknown','Unknown','Cannot determine encryption posture.',0.50,90)
ON CONFLICT (enum_type, control_type, code) DO NOTHING;


-- 6) VULN / EXPLOIT SIGNAL --------------------------------------------------
CREATE TABLE IF NOT EXISTS public.vuln_exploit_signal_metadata (
  enum_type        TEXT    NOT NULL,              -- 'exploit_signal' | 'severity_tier'
  control_type     TEXT    NOT NULL DEFAULT 'COMMON',  -- 'SOC2' | 'HIPAA' | 'COMMON'
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  likelihood_modifier NUMERIC(6,3),               -- optional calibration hint
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, control_type, code)
);

-- Add control_type column if table already exists (idempotent migration)
ALTER TABLE public.vuln_exploit_signal_metadata
  ADD COLUMN IF NOT EXISTS control_type TEXT NOT NULL DEFAULT 'COMMON';

-- Replace PK to include control_type (idempotent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public' AND table_name = 'vuln_exploit_signal_metadata'
    AND constraint_type = 'PRIMARY KEY'
    AND constraint_name = 'vuln_exploit_signal_metadata_pkey'
  ) THEN
    IF (SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'vuln_exploit_signal_metadata'
        AND constraint_name = 'vuln_exploit_signal_metadata_pkey') < 3 THEN
      EXECUTE 'ALTER TABLE public.vuln_exploit_signal_metadata DROP CONSTRAINT vuln_exploit_signal_metadata_pkey';
      EXECUTE 'ALTER TABLE public.vuln_exploit_signal_metadata ADD CONSTRAINT vuln_exploit_signal_metadata_pkey PRIMARY KEY (enum_type, control_type, code)';
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_vuln_exploit_signal_metadata_control_type
  ON public.vuln_exploit_signal_metadata (control_type, enum_type);

INSERT INTO public.vuln_exploit_signal_metadata
(enum_type, control_type, code, display_name, description, likelihood_modifier, sort_order)
VALUES
  -- Exploit evidence fusion
  ('exploit_signal','COMMON','kev_confirmed','KEV confirmed','CISA Known Exploited Vulnerabilities indicates active exploitation in the wild.',1.50,10),
  ('exploit_signal','COMMON','public_exploit','Public exploit','Exploit available publicly (e.g., ExploitDB/metasploit).',1.30,20),
  ('exploit_signal','COMMON','poc_only','PoC only','Proof-of-concept exists; weaponization uncertain.',1.15,30),
  ('exploit_signal','COMMON','no_known_exploit','No known exploit','No exploit evidence available.',1.00,40),
  ('exploit_signal','COMMON','unknown','Unknown','Exploit evidence unknown or not enriched.',1.05,90),

  -- Severity tiers (if you want to map CVSS -> tier consistently)
  ('severity_tier','COMMON','critical','Critical','Highest severity tier (e.g., CVSS >= 9.0).',NULL,10),
  ('severity_tier','COMMON','high','High','High severity tier (e.g., CVSS 7.0–8.9).',NULL,20),
  ('severity_tier','COMMON','medium','Medium','Medium severity tier (e.g., CVSS 4.0–6.9).',NULL,30),
  ('severity_tier','COMMON','low','Low','Low severity tier (e.g., CVSS 0.1–3.9).',NULL,40),
  ('severity_tier','COMMON','unknown','Unknown','Severity not determined.',NULL,90)
ON CONFLICT (enum_type, control_type, code) DO NOTHING;


-- 7) CONTROL EXCEPTIONS -----------------------------------------------------
CREATE TABLE IF NOT EXISTS public.control_exception_metadata (
  enum_type        TEXT    NOT NULL,              -- 'exception_type'|'exception_status'|'exception_expiry_bucket'
  control_type     TEXT    NOT NULL DEFAULT 'COMMON',  -- 'SOC2' | 'HIPAA' | 'COMMON'
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  min_days         INT,
  max_days         INT,
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, control_type, code)
);

-- Add control_type column if table already exists (idempotent migration)
ALTER TABLE public.control_exception_metadata
  ADD COLUMN IF NOT EXISTS control_type TEXT NOT NULL DEFAULT 'COMMON';

-- Replace PK to include control_type (idempotent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public' AND table_name = 'control_exception_metadata'
    AND constraint_type = 'PRIMARY KEY'
    AND constraint_name = 'control_exception_metadata_pkey'
  ) THEN
    IF (SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'control_exception_metadata'
        AND constraint_name = 'control_exception_metadata_pkey') < 3 THEN
      EXECUTE 'ALTER TABLE public.control_exception_metadata DROP CONSTRAINT control_exception_metadata_pkey';
      EXECUTE 'ALTER TABLE public.control_exception_metadata ADD CONSTRAINT control_exception_metadata_pkey PRIMARY KEY (enum_type, control_type, code)';
    END IF;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_control_exception_metadata_control_type
  ON public.control_exception_metadata (control_type, enum_type);

INSERT INTO public.control_exception_metadata
(enum_type, control_type, code, display_name, description, min_days, max_days, sort_order)
VALUES
  ('exception_type','COMMON','risk_acceptance','Risk acceptance','Approved acceptance of risk for a defined period.',NULL,NULL,10),
  ('exception_type','COMMON','false_positive','False positive','Control/vuln signal determined to be false positive.',NULL,NULL,20),
  ('exception_type','COMMON','business_need','Business need','Exception granted due to business constraints.',NULL,NULL,30),
  ('exception_type','COMMON','technical_constraint','Technical constraint','Exception due to technical limitations/legacy constraints.',NULL,NULL,40),

  ('exception_status','COMMON','approved','Approved','Exception is approved and currently valid.',NULL,NULL,10),
  ('exception_status','COMMON','pending','Pending','Exception request submitted but not approved.',NULL,NULL,20),
  ('exception_status','COMMON','expired','Expired','Exception window has ended; should be remediated.',NULL,NULL,30),
  ('exception_status','COMMON','rejected','Rejected','Exception request denied.',NULL,NULL,40),

  ('exception_expiry_bucket','COMMON','lt_7d','< 7 days','Exception expires in under 7 days.',0,7,10),
  ('exception_expiry_bucket','COMMON','7_30d','7–30 days','Exception expires in 7–30 days.',7,30,20),
  ('exception_expiry_bucket','COMMON','30_90d','30–90 days','Exception expires in 30–90 days.',30,90,30),
  ('exception_expiry_bucket','COMMON','gt_90d','> 90 days','Exception expires in more than 90 days.',90,NULL,40),
  ('exception_expiry_bucket','COMMON','none','No expiry','Exception has no defined expiry (discouraged).',NULL,NULL,90)
ON CONFLICT (enum_type, control_type, code) DO NOTHING;



-- =====================================================================================
-- 8) RISK DRIVER (EXPLAINABILITY)
-- =====================================================================================
-- Purpose: Captures the PRIMARY reasons an asset's risk score is elevated.
--          Used for human-readable explainability, dashboards, and remediation prioritization.
--
-- How it works:
--   * Each risk_driver_primary code represents a distinct "why" behind elevated risk.
--   * category_hint groups drivers into buckets: 'control', 'likelihood', 'impact', 'scope', 'unknown'.
--   * The transform layer assigns one or more drivers to each asset based on signal fusion.
--   * Consumers (dashboards, reports, agents) query this table to display driver labels/descriptions.
--
-- Usage by agents:
--   * risk_agent          → selects drivers to explain overall risk posture.
--   * impact_agent        → filters drivers where category_hint = 'impact'.
--   * likelihood_agent    → filters drivers where category_hint = 'likelihood'.
--   * remediation_agent   → ranks drivers by sort_order to prioritize fix actions.
--
-- Notes:
--   * sort_order defines default display priority (lower = higher priority).
--   * Extend with new codes as new detection rules are added; do NOT remove existing codes.
/* -- =====================================================================================
CREATE TABLE IF NOT EXISTS public.risk_driver_metadata (
  enum_type        TEXT    NOT NULL DEFAULT 'risk_driver_primary',
  code             TEXT    NOT NULL,
  display_name     TEXT    NOT NULL,
  description      TEXT,
  category_hint    TEXT,                           -- optional grouping (likelihood/impact/control)
  sort_order       INT     NOT NULL DEFAULT 0,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (enum_type, code)
);

INSERT INTO public.risk_driver_metadata
(enum_type, code, display_name, description, category_hint, sort_order)
VALUES
  ('risk_driver_primary','monitoring_gap','Monitoring gap','Telemetry stale/absent; cannot prove operating effectiveness.', 'control',10),
  ('risk_driver_primary','endpoint_control_gap','Endpoint control gap','Missing/weak EDR/AV/encryption posture.', 'control',20),
  ('risk_driver_primary','hardening_gap','Hardening gap','OS/config hardening gaps (secure boot off, legacy protocols, etc.).','control',30),
  ('risk_driver_primary','exploitable_vuln','Exploitable vulnerability','Exploit evidence present (KEV/public exploit/PoC).','likelihood',40),
  ('risk_driver_primary','encryption_gap','Encryption gap','Encryption missing or partial on regulated endpoints.', 'control',50),
  ('risk_driver_primary','unknown','Unknown','Driver not classified; needs rules/tags/ownership.', 'unknown',90)
ON CONFLICT (enum_type, code) DO NOTHING; */

-- =====================================================================================
-- Add framework-scoped risk drivers while keeping a SHARED enum_type = 'risk_driver_primary'
-- Goal: query by framework (SOC2 vs HIPAA) without duplicating enum types.
-- Approach:
--   1) Add a "framework" column
--   2) Expand PK to (enum_type, framework, code)
--   3) Seed rows for SOC2 + HIPAA (plus an optional 'COMMON' set)
-- =====================================================================================

-- 0) If risk_driver_metadata already exists from prior script
-- Add framework column (idempotent)
ALTER TABLE public.risk_driver_metadata
  ADD COLUMN IF NOT EXISTS framework TEXT NOT NULL DEFAULT 'COMMON';

-- 1) Replace the existing PK with a composite PK including framework
-- (Safe sequence: drop old PK constraint if it exists, then add new one)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM   information_schema.table_constraints
    WHERE  table_schema = 'public'
    AND    table_name   = 'risk_driver_metadata'
    AND    constraint_type = 'PRIMARY KEY'
  ) THEN
    EXECUTE 'ALTER TABLE public.risk_driver_metadata DROP CONSTRAINT risk_driver_metadata_pkey';
  END IF;
END $$;

ALTER TABLE public.risk_driver_metadata
  ADD CONSTRAINT risk_driver_metadata_pkey PRIMARY KEY (enum_type, framework, code);

-- 2) Optional: helpful index for fast filtering by framework
CREATE INDEX IF NOT EXISTS idx_risk_driver_metadata_framework
  ON public.risk_driver_metadata (framework, enum_type);

-- 3) Seed data: COMMON drivers (framework-neutral)
INSERT INTO public.risk_driver_metadata
(enum_type, framework, code, display_name, description, category_hint, sort_order, is_active)
VALUES
  ('risk_driver_primary','COMMON','monitoring_gap','Monitoring gap',
   'Telemetry stale/absent; cannot prove operating effectiveness.', 'control',10,TRUE),

  ('risk_driver_primary','COMMON','endpoint_control_gap','Endpoint control gap',
   'Missing/weak EDR/AV/encryption posture for the asset.', 'control',20,TRUE),

  ('risk_driver_primary','COMMON','hardening_gap','Hardening gap',
   'OS/config hardening drift (secure boot disabled, legacy protocols, risky scripting policy).', 'control',30,TRUE),

  ('risk_driver_primary','COMMON','exploitable_vuln','Exploitable vulnerability',
   'Exploit evidence present (KEV/public exploit/PoC) and exposure remains open.', 'likelihood',40,TRUE),

  ('risk_driver_primary','COMMON','encryption_gap','Encryption gap',
   'Encryption missing or partial on endpoints where confidentiality expectations apply.', 'control',50,TRUE),

  ('risk_driver_primary','COMMON','scope_unknown','Scope unknown',
   'Asset scope/owner/classification unknown; cannot apply correct control expectations.', 'scope',60,TRUE),

  ('risk_driver_primary','COMMON','unknown','Unknown',
   'Driver not classified; requires rule tuning, ownership, or enrichment.', 'unknown',99,TRUE)
ON CONFLICT (enum_type, framework, code) DO NOTHING;

-- 4) Seed data: SOC2-specific drivers (same enum_type, framework='SOC2')
INSERT INTO public.risk_driver_metadata
(enum_type, framework, code, display_name, description, category_hint, sort_order, is_active)
VALUES
  ('risk_driver_primary','SOC2','monitoring_gap','Monitoring gap (SOC2)',
   'Monitoring/telemetry gaps reduce assurance and increase probability of undetected incidents for SOC2 trust criteria.', 'control',10,TRUE),

  ('risk_driver_primary','SOC2','endpoint_control_gap','Endpoint control gap (SOC2)',
   'Missing/weak endpoint controls (EDR/AV) increase security incident likelihood under SOC2 security criteria.', 'control',20,TRUE),

  ('risk_driver_primary','SOC2','hardening_gap','Hardening gap (SOC2)',
   'Security baseline/hardening drift undermines SOC2 logical access and system operations expectations.', 'control',30,TRUE),

  ('risk_driver_primary','SOC2','exploitable_vuln','Exploitable vulnerability (SOC2)',
   'Known exploitation signals (KEV/public exploit) materially increase incident likelihood relevant to SOC2.', 'likelihood',40,TRUE),

  ('risk_driver_primary','SOC2','change_hygiene_gap','Change/patch hygiene gap (SOC2)',
   'Signals of deferred maintenance (reboot pending, extreme uptime, old BIOS/OS) suggest patch/control drift.', 'control',50,TRUE),

  ('risk_driver_primary','SOC2','privileged_access_node','Privileged access node risk (SOC2)',
   'Bastion/PAW or privileged access infrastructure elevates impact of compromise under SOC2.', 'impact',60,TRUE),

  ('risk_driver_primary','SOC2','scope_unknown','Scope unknown (SOC2)',
   'SOC2 boundary/scope not determined; ownership/tags missing.', 'scope',90,TRUE)
ON CONFLICT (enum_type, framework, code) DO NOTHING;

-- 5) Seed data: HIPAA-specific drivers (same enum_type, framework='HIPAA')
INSERT INTO public.risk_driver_metadata
(enum_type, framework, code, display_name, description, category_hint, sort_order, is_active)
VALUES
  ('risk_driver_primary','HIPAA','monitoring_gap','Monitoring gap (HIPAA)',
   'Telemetry gaps reduce ability to detect unauthorized access and support audit controls expectations.', 'control',10,TRUE),

  ('risk_driver_primary','HIPAA','endpoint_control_gap','Endpoint protection gap (HIPAA)',
   'Missing/weak endpoint protections increase probability of compromise affecting confidentiality/integrity of regulated systems.', 'control',20,TRUE),

  ('risk_driver_primary','HIPAA','hardening_gap','Hardening gap (HIPAA)',
   'Hardening drift (legacy protocols, risky scripting, secure boot disabled) increases unauthorized disclosure risk.', 'control',30,TRUE),

  ('risk_driver_primary','HIPAA','exploitable_vuln','Exploitable vulnerability (HIPAA)',
   'Exploit evidence (KEV/public exploit) increases likelihood of breach impacting ePHI systems.', 'likelihood',40,TRUE),

  ('risk_driver_primary','HIPAA','encryption_gap','Encryption gap (HIPAA)',
   'Disk encryption missing/unknown materially increases disclosure impact for lost/stolen endpoints and data-at-rest exposure.', 'impact',50,TRUE),

  ('risk_driver_primary','HIPAA','internet_exposure','Internet exposure (HIPAA)',
   'Externally exposed regulated assets increase breach likelihood and disclosure scope.', 'impact',60,TRUE),

  ('risk_driver_primary','HIPAA','scope_unknown','Scope unknown (HIPAA)',
   'HIPAA/ePHI scope not determined; requires dataflow mapping/ownership confirmation.', 'scope',90,TRUE)
ON CONFLICT (enum_type, framework, code) DO NOTHING;

-- 6) (Optional) Normalize existing rows that may have been inserted earlier without framework
-- If you previously inserted into risk_driver_metadata without framework, those rows now defaulted to 'COMMON'.
-- This is fine; no action needed unless you want a different default.

CREATE OR REPLACE VIEW public.risk_driver_metadata_resolved AS
SELECT
  CASE
    WHEN framework = 'SOC2' THEN 'risk_driver_primary_SOC2'
    WHEN framework = 'HIPAA' THEN 'risk_driver_primary_HIPAA'
    ELSE 'risk_driver_primary_COMMON'
  END AS enum_type,
  code,
  display_name,
  description,
  category_hint,
  sort_order,
  is_active
FROM public.risk_driver_metadata;

