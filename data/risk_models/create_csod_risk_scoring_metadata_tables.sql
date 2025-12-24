-- ============================================================================
-- CSOD Risk Scoring Metadata Tables
-- ============================================================================
-- Purpose
-- -------
-- Create a small set of reusable metadata tables to drive the calculations
-- described in `data/risk_models/csod_risk_timeseries.md` and the CSOD risk MDLs:
-- - ComplianceRisk_Silver: riskScore = sqrt(impactScore * likelihoodScore)
-- - AttritionRisk_Silver : attritionRiskScore = sqrt(attritionImpactScore * attritionLikelihoodScore)
--
-- These metadata tables allow you to:
-- - Define which factors contribute to impact vs likelihood per model
-- - Map categorical inputs to scores (lookup tables)
-- - Bucket numeric inputs into scores (bucket tables)
-- - Define score bands (Low/Moderate/High/Critical)
-- - Define escalation rules (e.g., risk > 75 OR daysUntilDue < 7)
--
-- Notes
-- -----
-- - Tables are created in the *current schema* (no explicit schema prefix),
--   matching existing migrations (e.g., `data/cvedata/migrations/create_enum_metadata_tables.sql`).
-- - Seed values below are intentionally conservative defaults; adjust weights/buckets
--   to match your production calibration and business expectations.
-- ============================================================================

-- ============================================================================
-- 1) Models
-- ============================================================================
CREATE TABLE IF NOT EXISTS csod_risk_model_metadata (
    id SERIAL PRIMARY KEY,
    model_code VARCHAR(50) UNIQUE NOT NULL, -- 'compliance' | 'attrition'
    description TEXT,
    risk_formula VARCHAR(200) NOT NULL DEFAULT 'sqrt(impact_score * likelihood_score)',
    score_min DECIMAL(10,2) NOT NULL DEFAULT 0.0,
    score_max DECIMAL(10,2) NOT NULL DEFAULT 100.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO csod_risk_model_metadata (model_code, description, risk_formula) VALUES
    ('compliance', 'CSOD compliance non-completion risk model (riskScore = sqrt(impactScore * likelihoodScore))', 'sqrt(impact_score * likelihood_score)'),
    ('attrition',  'CSOD employee attrition risk model (attritionRiskScore = sqrt(attritionImpactScore * attritionLikelihoodScore))', 'sqrt(impact_score * likelihood_score)')
ON CONFLICT (model_code) DO NOTHING;

-- ============================================================================
-- 2) Score bands (riskCategory / riskCategory)
-- ============================================================================
CREATE TABLE IF NOT EXISTS csod_risk_score_band_metadata (
    id SERIAL PRIMARY KEY,
    model_code VARCHAR(50) NOT NULL,
    band_code VARCHAR(50) NOT NULL, -- 'Low' | 'Moderate' | 'High' | 'Critical'
    min_score DECIMAL(10,2) NOT NULL,
    max_score DECIMAL(10,2) NOT NULL,
    priority_order INTEGER NOT NULL, -- 1 = highest severity
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_code, band_code)
);

CREATE INDEX IF NOT EXISTS idx_csod_risk_score_band_model ON csod_risk_score_band_metadata(model_code);
CREATE INDEX IF NOT EXISTS idx_csod_risk_score_band_range ON csod_risk_score_band_metadata(min_score, max_score);

-- Thresholds are aligned to the CSOD risk MDLs:
-- Low (0-25), Moderate (25-50), High (50-75), Critical (75-100)
INSERT INTO csod_risk_score_band_metadata (model_code, band_code, min_score, max_score, priority_order, description) VALUES
    ('compliance', 'Critical', 75.0, 100.0, 1, 'Critical compliance risk (75-100)'),
    ('compliance', 'High',     50.0,  75.0, 2, 'High compliance risk (50-75)'),
    ('compliance', 'Moderate', 25.0,  50.0, 3, 'Moderate compliance risk (25-50)'),
    ('compliance', 'Low',       0.0,  25.0, 4, 'Low compliance risk (0-25)'),
    ('attrition',  'Critical', 75.0, 100.0, 1, 'Critical attrition risk (75-100)'),
    ('attrition',  'High',     50.0,  75.0, 2, 'High attrition risk (50-75)'),
    ('attrition',  'Moderate', 25.0,  50.0, 3, 'Moderate attrition risk (25-50)'),
    ('attrition',  'Low',       0.0,  25.0, 4, 'Low attrition risk (0-25)')
ON CONFLICT (model_code, band_code) DO NOTHING;

-- ============================================================================
-- 3) Factors (what contributes to impact vs likelihood)
-- ============================================================================
CREATE TABLE IF NOT EXISTS csod_risk_factor_metadata (
    id SERIAL PRIMARY KEY,
    model_code VARCHAR(50) NOT NULL,              -- 'compliance' | 'attrition'
    dimension VARCHAR(20) NOT NULL,               -- 'impact' | 'likelihood'
    factor_code VARCHAR(100) NOT NULL,            -- stable identifier used by the pipeline
    factor_name VARCHAR(200) NOT NULL,
    description TEXT,
    source_tables TEXT,                           -- documentation only (comma-separated)
    source_columns TEXT,                          -- documentation only (comma-separated)
    scoring_type VARCHAR(30) NOT NULL,            -- 'bucket' | 'lookup' | 'linear' | 'rule'
    default_score DECIMAL(10,2),                  -- used if input is null/unmapped
    weight DECIMAL(5,3) NOT NULL DEFAULT 1.0,     -- relative weight within (model_code, dimension)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_code, dimension, factor_code)
);

CREATE INDEX IF NOT EXISTS idx_csod_risk_factor_model_dim ON csod_risk_factor_metadata(model_code, dimension);
CREATE INDEX IF NOT EXISTS idx_csod_risk_factor_active ON csod_risk_factor_metadata(is_active);

-- Compliance: impact factors (primarily Activity_csod + User_csod context)
INSERT INTO csod_risk_factor_metadata
  (model_code, dimension, factor_code, factor_name, description, source_tables, source_columns, scoring_type, default_score, weight)
VALUES
  ('compliance', 'impact', 'activity_type', 'Activity Type Impact', 'Higher impact for compliance/regulatory activities', 'Activity_csod', 'activityType,isCompliance,isCertification', 'lookup', 60.0, 0.50),
  ('compliance', 'impact', 'estimated_duration', 'Estimated Duration Impact', 'Longer mandatory trainings have higher business impact if missed', 'Activity_csod', 'estimatedDuration', 'bucket', 50.0, 0.20),
  ('compliance', 'impact', 'activity_cost', 'Activity Cost Impact', 'Higher financial cost increases impact of non-completion', 'Activity_csod', 'cost', 'bucket', 40.0, 0.20),
  ('compliance', 'impact', 'position_level', 'Position Level Impact', 'More senior roles have higher compliance impact', 'User_csod', 'position (derived positionLevel)', 'lookup', 60.0, 0.10)
ON CONFLICT (model_code, dimension, factor_code) DO NOTHING;

-- Compliance: likelihood factors (primarily ComplianceRisk_Silver columns)
INSERT INTO csod_risk_factor_metadata
  (model_code, dimension, factor_code, factor_name, description, source_tables, source_columns, scoring_type, default_score, weight)
VALUES
  ('compliance', 'likelihood', 'days_until_due', 'Days Until Due Likelihood', 'Likelihood increases as deadline approaches; overdue is highest (with additional granularity by how many days overdue)', 'ComplianceRisk_Silver', 'daysUntilDue', 'bucket', 50.0, 0.20),
  ('compliance', 'likelihood', 'completion_percentage', 'Completion Percentage Likelihood', 'Lower completion % implies higher probability of non-completion', 'ComplianceRisk_Silver', 'completionPercentage', 'bucket', 60.0, 0.26),
  ('compliance', 'likelihood', 'course_completion_status', 'Course Completion Status Likelihood', 'Status of the course attempt (Assigned/In Progress/Completed/Overdue) influences probability of missing the deadline', 'Transcript_csod', 'trainingStatus,isCompleted,isOverdue', 'lookup', 70.0, 0.05),
  ('compliance', 'likelihood', 'days_since_last_activity_start', 'Days Since Last Activity Started Likelihood', 'Long time since starting an attempt without completion suggests stalling and increased non-completion likelihood', 'Transcript_csod,Activity_csod', 'attemptStartDate,activityStartDate', 'bucket', 80.0, 0.05),
  ('compliance', 'likelihood', 'user_completion_rate', 'Historical User Completion Likelihood', 'Users with low historical completion have higher likelihood of non-completion', 'ComplianceRisk_Silver', 'userCompletionRate', 'bucket', 55.0, 0.11),
  ('compliance', 'likelihood', 'last_login_days', 'Days Since Last Login Likelihood', 'Higher inactivity on LMS increases non-completion likelihood', 'ComplianceRisk_Silver,User_csod', 'lastLoginDays,lastLoginDate', 'bucket', 40.0, 0.10),
  ('compliance', 'likelihood', 'previous_attempts', 'Previous Attempts Likelihood', 'Repeated incomplete attempts indicate higher likelihood of missing the deadline', 'ComplianceRisk_Silver,Transcript_csod', 'previousAttempts', 'bucket', 30.0, 0.05),
  ('compliance', 'likelihood', 'days_since_assigned', 'Days Since Assigned Likelihood', 'Long-running assignments (days since assigned) indicate delayed completion risk, especially when progress is low', 'ComplianceRisk_Silver', 'daysSinceAssigned', 'bucket', 35.0, 0.05),
  ('compliance', 'likelihood', 'division_completion_rate', 'Division Completion Rate Context', 'Division-level completion performance (culture/process) provides contextual signal for individual completion likelihood', 'ComplianceRisk_Division', 'completionRate', 'bucket', 70.0, 0.06),
  ('compliance', 'likelihood', 'division_overdue_rate', 'Division Overdue Rate Context', 'Division-level overdue rate provides systemic compliance signal that affects individual likelihood', 'ComplianceRisk_Division', 'overdueCount,totalAssignments (derived rate)', 'bucket', 60.0, 0.04),
  ('compliance', 'likelihood', 'division_avg_days_to_complete', 'Division Avg Days To Complete Context', 'Division-level speed of completion provides contextual signal for time-to-completion risk', 'ComplianceRisk_Division', 'avgDaysToComplete', 'bucket', 50.0, 0.03)
ON CONFLICT (model_code, dimension, factor_code) DO NOTHING;

-- Keep weights stable if this script is re-run after initial inserts
UPDATE csod_risk_factor_metadata
SET weight = 0.20
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'days_until_due';

UPDATE csod_risk_factor_metadata
SET weight = 0.26
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'completion_percentage';

UPDATE csod_risk_factor_metadata
SET weight = 0.05
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'course_completion_status';

UPDATE csod_risk_factor_metadata
SET weight = 0.05
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'days_since_last_activity_start';

UPDATE csod_risk_factor_metadata
SET weight = 0.11
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'user_completion_rate';

UPDATE csod_risk_factor_metadata
SET weight = 0.10
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'last_login_days';

UPDATE csod_risk_factor_metadata
SET weight = 0.05
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'previous_attempts';

UPDATE csod_risk_factor_metadata
SET weight = 0.05
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'days_since_assigned';

UPDATE csod_risk_factor_metadata
SET weight = 0.06
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'division_completion_rate';

UPDATE csod_risk_factor_metadata
SET weight = 0.04
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'division_overdue_rate';

UPDATE csod_risk_factor_metadata
SET weight = 0.03
WHERE model_code = 'compliance' AND dimension = 'likelihood' AND factor_code = 'division_avg_days_to_complete';

-- Attrition: impact factors
INSERT INTO csod_risk_factor_metadata
  (model_code, dimension, factor_code, factor_name, description, source_tables, source_columns, scoring_type, default_score, weight)
VALUES
  ('attrition', 'impact', 'position_level', 'Position Level Impact', 'Higher level roles have higher organizational impact if they leave', 'AttritionRisk_Silver,User_csod', 'positionLevel,position', 'lookup', 60.0, 0.45),
  ('attrition', 'impact', 'direct_report_count', 'Direct Report Count Impact', 'Managers affect more people; more direct reports => higher impact', 'AttritionRisk_Silver,User_csod', 'directReportCount', 'bucket', 40.0, 0.25),
  ('attrition', 'impact', 'training_investment', 'Training Investment Impact', 'Higher sunk training investment increases impact of attrition', 'AttritionRisk_Silver,Activity_csod', 'trainingInvestment,cost', 'bucket', 30.0, 0.30)
ON CONFLICT (model_code, dimension, factor_code) DO NOTHING;

-- Attrition: likelihood factors
INSERT INTO csod_risk_factor_metadata
  (model_code, dimension, factor_code, factor_name, description, source_tables, source_columns, scoring_type, default_score, weight)
VALUES
  ('attrition', 'likelihood', 'tenure_risk_band', 'Tenure Risk Band Likelihood', 'Known vulnerability windows by tenure', 'AttritionRisk_Silver', 'tenureRiskBand,tenureMonths', 'lookup', 50.0, 0.17),
  ('attrition', 'likelihood', 'learning_engagement', 'Learning Engagement Likelihood', 'Low engagement is an inverse predictor of retention', 'AttritionRisk_Silver', 'learningEngagementScore', 'bucket', 50.0, 0.22),
  ('attrition', 'likelihood', 'compliance_completion_rate', 'Compliance Completion Rate Likelihood', 'Low compliance completion can indicate disengagement / pre-departure behavior', 'AttritionRisk_Silver', 'complianceCompletionRate', 'bucket', 45.0, 0.12),
  ('attrition', 'likelihood', 'course_completion_rate', 'Course Completion Rate Likelihood', 'Recent overall course completion rate (not only compliance) can indicate engagement/intent to stay', 'Transcript_csod', 'isCompleted,trainingStatus (derived completion rate)', 'bucket', 55.0, 0.05),
  ('attrition', 'likelihood', 'completion_percentage', 'Course Completion Percentage Likelihood', 'Average completion progress on active assignments; stalling at low completion can signal disengagement', 'ComplianceRisk_Silver,Transcript_csod', 'completionPercentage', 'bucket', 60.0, 0.04),
  ('attrition', 'likelihood', 'days_since_last_activity_start', 'Days Since Last Activity Started Likelihood', 'Long time since starting an attempt without completion can signal disengagement', 'Transcript_csod,Activity_csod', 'attemptStartDate,activityStartDate', 'bucket', 70.0, 0.03),
  ('attrition', 'likelihood', 'last_login_days', 'Days Since Last Login Likelihood', 'Extended inactivity suggests disengagement', 'AttritionRisk_Silver,User_csod', 'lastLoginDays,lastLoginDate', 'bucket', 35.0, 0.08),
  ('attrition', 'likelihood', 'overdue_course_count', 'Overdue Course Count Likelihood', 'More overdue courses correlate with disengagement', 'AttritionRisk_Silver,Transcript_csod', 'overdueCourseCount,isOverdue', 'bucket', 30.0, 0.18),
  ('attrition', 'likelihood', 'manager_change_count', 'Manager Change Count Likelihood', 'Frequent manager changes correlate with attrition', 'AttritionRisk_Silver,User_csod', 'managerChangeCount,managerId', 'bucket', 20.0, 0.08),
  ('attrition', 'likelihood', 'division_completion_rate', 'Division Completion Rate Context', 'Division-level completion performance provides contextual signal for individual engagement and attrition likelihood', 'ComplianceRisk_Division', 'completionRate', 'bucket', 70.0, 0.03),
  ('attrition', 'likelihood', 'division_overdue_rate', 'Division Overdue Rate Context', 'Division-level overdue rate provides contextual disengagement signal', 'ComplianceRisk_Division', 'overdueCount,totalAssignments (derived rate)', 'bucket', 60.0, 0.03)
ON CONFLICT (model_code, dimension, factor_code) DO NOTHING;

-- Keep weights stable for attrition likelihood (re-runnable)
UPDATE csod_risk_factor_metadata SET weight = 0.17 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='tenure_risk_band';
UPDATE csod_risk_factor_metadata SET weight = 0.22 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='learning_engagement';
UPDATE csod_risk_factor_metadata SET weight = 0.12 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='compliance_completion_rate';
UPDATE csod_risk_factor_metadata SET weight = 0.05 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='course_completion_rate';
UPDATE csod_risk_factor_metadata SET weight = 0.04 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='completion_percentage';
UPDATE csod_risk_factor_metadata SET weight = 0.03 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='days_since_last_activity_start';
UPDATE csod_risk_factor_metadata SET weight = 0.08 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='last_login_days';
UPDATE csod_risk_factor_metadata SET weight = 0.18 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='overdue_course_count';
UPDATE csod_risk_factor_metadata SET weight = 0.08 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='manager_change_count';
UPDATE csod_risk_factor_metadata SET weight = 0.03 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='division_completion_rate';
UPDATE csod_risk_factor_metadata SET weight = 0.03 WHERE model_code='attrition' AND dimension='likelihood' AND factor_code='division_overdue_rate';

-- ============================================================================
-- 4) Lookup mappings (categorical -> score)
-- ============================================================================
CREATE TABLE IF NOT EXISTS csod_risk_factor_lookup_metadata (
    id SERIAL PRIMARY KEY,
    model_code VARCHAR(50) NOT NULL,
    dimension VARCHAR(20) NOT NULL,
    factor_code VARCHAR(100) NOT NULL,
    input_value VARCHAR(200) NOT NULL,
    score DECIMAL(10,2) NOT NULL,            -- 0-100
    priority_order INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_code, dimension, factor_code, input_value)
);

CREATE INDEX IF NOT EXISTS idx_csod_lookup_factor ON csod_risk_factor_lookup_metadata(model_code, dimension, factor_code);

-- Compliance impact: activity type
INSERT INTO csod_risk_factor_lookup_metadata
  (model_code, dimension, factor_code, input_value, score, priority_order, description)
VALUES
  ('compliance', 'impact', 'activity_type', 'Compliance',     100.0, 1, 'Regulatory/compliance required'),
  ('compliance', 'impact', 'activity_type', 'Certification',   85.0, 2, 'Certification required/important'),
  ('compliance', 'impact', 'activity_type', 'Training',        60.0, 3, 'General training'),
  ('compliance', 'impact', 'activity_type', 'Other',           50.0, 4, 'Other activity type')
ON CONFLICT (model_code, dimension, factor_code, input_value) DO NOTHING;

-- Compliance likelihood: course completion status (Transcript_csod.trainingStatus)
INSERT INTO csod_risk_factor_lookup_metadata
  (model_code, dimension, factor_code, input_value, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'course_completion_status', 'Completed',    0.0,  1, 'Already completed'),
  ('compliance', 'likelihood', 'course_completion_status', 'In Progress', 45.0, 2, 'Started; may still miss deadline'),
  ('compliance', 'likelihood', 'course_completion_status', 'Assigned',    75.0, 3, 'Not started; higher miss probability'),
  ('compliance', 'likelihood', 'course_completion_status', 'Overdue',     98.0, 4, 'Past due; near-certain non-completion on time')
ON CONFLICT (model_code, dimension, factor_code, input_value) DO UPDATE SET
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Shared: position level mapping (used by both models)
INSERT INTO csod_risk_factor_lookup_metadata
  (model_code, dimension, factor_code, input_value, score, priority_order, description)
VALUES
  ('compliance', 'impact', 'position_level', 'Executive',           100.0, 1, 'Executive role'),
  ('compliance', 'impact', 'position_level', 'Senior Management',    90.0, 2, 'Senior management'),
  ('compliance', 'impact', 'position_level', 'Middle Management',    75.0, 3, 'Middle management'),
  ('compliance', 'impact', 'position_level', 'Individual Contributor', 60.0, 4, 'Individual contributor'),
  ('compliance', 'impact', 'position_level', 'Entry Level',          40.0, 5, 'Entry level'),
  ('attrition',  'impact', 'position_level', 'Executive',           100.0, 1, 'Executive role'),
  ('attrition',  'impact', 'position_level', 'Senior Management',    90.0, 2, 'Senior management'),
  ('attrition',  'impact', 'position_level', 'Middle Management',    75.0, 3, 'Middle management'),
  ('attrition',  'impact', 'position_level', 'Individual Contributor', 60.0, 4, 'Individual contributor'),
  ('attrition',  'impact', 'position_level', 'Entry Level',          40.0, 5, 'Entry level')
ON CONFLICT (model_code, dimension, factor_code, input_value) DO NOTHING;

-- Attrition likelihood: tenure risk band
INSERT INTO csod_risk_factor_lookup_metadata
  (model_code, dimension, factor_code, input_value, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'tenure_risk_band', 'New Hire Critical (0-6mo)',  80.0, 1, 'Highest vulnerability window'),
  ('attrition', 'likelihood', 'tenure_risk_band', 'Post-Onboarding Risk (6-18mo)', 70.0, 2, 'Post-onboarding vulnerability'),
  ('attrition', 'likelihood', 'tenure_risk_band', 'Mid-Career Risk (18-36mo)',  60.0, 3, 'Mid-career vulnerability'),
  ('attrition', 'likelihood', 'tenure_risk_band', 'Stable (36mo+)',             30.0, 4, 'More stable cohort')
ON CONFLICT (model_code, dimension, factor_code, input_value) DO NOTHING;

-- ============================================================================
-- 5) Buckets (numeric -> score)
-- ============================================================================
CREATE TABLE IF NOT EXISTS csod_risk_factor_bucket_metadata (
    id SERIAL PRIMARY KEY,
    model_code VARCHAR(50) NOT NULL,
    dimension VARCHAR(20) NOT NULL,
    factor_code VARCHAR(100) NOT NULL,
    bucket_code VARCHAR(100) NOT NULL,
    min_value DECIMAL(18,6),
    max_value DECIMAL(18,6),
    min_inclusive BOOLEAN DEFAULT TRUE,
    max_inclusive BOOLEAN DEFAULT FALSE,
    score DECIMAL(10,2) NOT NULL,
    priority_order INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_code, dimension, factor_code, bucket_code)
);

CREATE INDEX IF NOT EXISTS idx_csod_bucket_factor ON csod_risk_factor_bucket_metadata(model_code, dimension, factor_code);
CREATE INDEX IF NOT EXISTS idx_csod_bucket_range ON csod_risk_factor_bucket_metadata(min_value, max_value);

-- Compliance likelihood: daysUntilDue (negative = overdue)
-- Remove the older coarse "OVERDUE" bucket (if present) so granular overdue buckets do not overlap.
DELETE FROM csod_risk_factor_bucket_metadata
WHERE model_code = 'compliance'
  AND dimension = 'likelihood'
  AND factor_code = 'days_until_due'
  AND bucket_code = 'OVERDUE';

INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  -- Overdue buckets (missed completion by days: 0/7/30/60/90+)
  ('compliance', 'likelihood', 'days_until_due', 'OVERDUE_90_PLUS', NULL, -90.0, TRUE, TRUE, 100.0, 1, 'Overdue by 90+ days (daysUntilDue <= -90)'),
  ('compliance', 'likelihood', 'days_until_due', 'OVERDUE_60_90',  -90.0, -60.0, FALSE, TRUE,  99.0, 2, 'Overdue by 60-89 days'),
  ('compliance', 'likelihood', 'days_until_due', 'OVERDUE_30_60',  -60.0, -30.0, FALSE, TRUE,  97.0, 3, 'Overdue by 30-59 days'),
  ('compliance', 'likelihood', 'days_until_due', 'OVERDUE_7_30',   -30.0,  -7.0, FALSE, TRUE,  95.0, 4, 'Overdue by 7-29 days'),
  ('compliance', 'likelihood', 'days_until_due', 'OVERDUE_0_7',     -7.0,   0.0, FALSE, FALSE, 92.0, 5, 'Overdue by <7 days (-6 to -1)'),

  -- Not overdue buckets (deadline proximity)
  ('compliance', 'likelihood', 'days_until_due', 'DUE_0_7',        0.0,    7.0, TRUE, FALSE, 90.0, 6, 'Due within 7 days'),
  ('compliance', 'likelihood', 'days_until_due', 'DUE_7_14',       7.0,   14.0, TRUE, FALSE, 75.0, 7, 'Due within 7-14 days'),
  ('compliance', 'likelihood', 'days_until_due', 'DUE_14_30',     14.0,   30.0, TRUE, FALSE, 55.0, 8, 'Due within 14-30 days'),
  ('compliance', 'likelihood', 'days_until_due', 'DUE_30_PLUS',   30.0, 10000.0, TRUE, FALSE, 25.0, 9, 'Due in >30 days')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Compliance likelihood: daysSinceLastActivityStart (derived from Transcript_csod.attemptStartDate or Activity_csod.activityStartDate)
-- Metric: number of days between assessmentDate and the user's most recent attemptStartDate (or start date). Null => use default_score from factor metadata.
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'days_since_last_activity_start', 'LAS_0_1',      0.0,    1.0, TRUE, FALSE, 20.0, 1, 'Started within last day (active)'),
  ('compliance', 'likelihood', 'days_since_last_activity_start', 'LAS_1_7',      1.0,    7.0, TRUE, FALSE, 40.0, 2, 'Started within last week'),
  ('compliance', 'likelihood', 'days_since_last_activity_start', 'LAS_7_30',     7.0,   30.0, TRUE, FALSE, 60.0, 3, 'Started 7-30 days ago'),
  ('compliance', 'likelihood', 'days_since_last_activity_start', 'LAS_30_60',   30.0,   60.0, TRUE, FALSE, 80.0, 4, 'Started 30-60 days ago (stalling)'),
  ('compliance', 'likelihood', 'days_since_last_activity_start', 'LAS_60_90',   60.0,   90.0, TRUE, FALSE, 90.0, 5, 'Started 60-90 days ago (high stall)'),
  ('compliance', 'likelihood', 'days_since_last_activity_start', 'LAS_90_PLUS', 90.0, 10000.0, TRUE, FALSE, 95.0, 6, 'Started 90+ days ago (very high stall)')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Compliance likelihood: daysSinceAssigned (delay buckets: 30/60/90+ days outstanding)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'days_since_assigned', 'ASSIGNED_0_7',     0.0,   7.0, TRUE, FALSE, 10.0, 1, 'Assigned within the last 7 days'),
  ('compliance', 'likelihood', 'days_since_assigned', 'ASSIGNED_7_30',    7.0,  30.0, TRUE, FALSE, 25.0, 2, 'Assigned 7-30 days ago'),
  ('compliance', 'likelihood', 'days_since_assigned', 'ASSIGNED_30_60',  30.0,  60.0, TRUE, FALSE, 45.0, 3, 'Assigned 30-60 days ago'),
  ('compliance', 'likelihood', 'days_since_assigned', 'ASSIGNED_60_90',  60.0,  90.0, TRUE, FALSE, 60.0, 4, 'Assigned 60-90 days ago'),
  ('compliance', 'likelihood', 'days_since_assigned', 'ASSIGNED_90_PLUS', 90.0, 10000.0, TRUE, FALSE, 75.0, 5, 'Assigned 90+ days ago')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Compliance likelihood: division completion rate context (ComplianceRisk_Division.completionRate)
-- Lower completion rate => higher likelihood for individuals in that division (systemic signal).
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'division_completion_rate', 'DCR_0_60',     0.0,  60.0, TRUE, FALSE, 85.0, 1, 'Division completion rate <60%'),
  ('compliance', 'likelihood', 'division_completion_rate', 'DCR_60_80',   60.0,  80.0, TRUE, FALSE, 65.0, 2, 'Division completion rate 60-80%'),
  ('compliance', 'likelihood', 'division_completion_rate', 'DCR_80_90',   80.0,  90.0, TRUE, FALSE, 45.0, 3, 'Division completion rate 80-90%'),
  ('compliance', 'likelihood', 'division_completion_rate', 'DCR_90_97',   90.0,  97.0, TRUE, FALSE, 25.0, 4, 'Division completion rate 90-97%'),
  ('compliance', 'likelihood', 'division_completion_rate', 'DCR_97_100',  97.0, 100.0, TRUE, TRUE,  10.0, 5, 'Division completion rate 97-100%')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Compliance likelihood: division overdue rate context (derived: overdueCount/totalAssignments * 100)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'division_overdue_rate', 'DOR_0_1',     0.0,   1.0, TRUE, FALSE, 10.0, 1, 'Division overdue rate <1%'),
  ('compliance', 'likelihood', 'division_overdue_rate', 'DOR_1_5',     1.0,   5.0, TRUE, FALSE, 35.0, 2, 'Division overdue rate 1-5%'),
  ('compliance', 'likelihood', 'division_overdue_rate', 'DOR_5_10',    5.0,  10.0, TRUE, FALSE, 55.0, 3, 'Division overdue rate 5-10%'),
  ('compliance', 'likelihood', 'division_overdue_rate', 'DOR_10_20',  10.0,  20.0, TRUE, FALSE, 75.0, 4, 'Division overdue rate 10-20%'),
  ('compliance', 'likelihood', 'division_overdue_rate', 'DOR_20_PLUS', 20.0, 100.0, TRUE, TRUE,  90.0, 5, 'Division overdue rate 20%+')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Compliance likelihood: division avg days to complete context (ComplianceRisk_Division.avgDaysToComplete)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'division_avg_days_to_complete', 'DDC_0_7',     0.0,   7.0, TRUE, FALSE, 10.0, 1, 'Avg completion <=7 days'),
  ('compliance', 'likelihood', 'division_avg_days_to_complete', 'DDC_7_14',    7.0,  14.0, TRUE, FALSE, 25.0, 2, 'Avg completion 7-14 days'),
  ('compliance', 'likelihood', 'division_avg_days_to_complete', 'DDC_14_30',  14.0,  30.0, TRUE, FALSE, 45.0, 3, 'Avg completion 14-30 days'),
  ('compliance', 'likelihood', 'division_avg_days_to_complete', 'DDC_30_60',  30.0,  60.0, TRUE, FALSE, 70.0, 4, 'Avg completion 30-60 days'),
  ('compliance', 'likelihood', 'division_avg_days_to_complete', 'DDC_60_PLUS', 60.0, 10000.0, TRUE, FALSE, 85.0, 5, 'Avg completion 60+ days')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Compliance likelihood: completionPercentage (higher completion => lower likelihood)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'completion_percentage', 'COMP_0_20',     0.0,  20.0, 90.0, 1, '0-20% complete'),
  ('compliance', 'likelihood', 'completion_percentage', 'COMP_20_50',   20.0,  50.0, 75.0, 2, '20-50% complete'),
  ('compliance', 'likelihood', 'completion_percentage', 'COMP_50_80',   50.0,  80.0, 50.0, 3, '50-80% complete'),
  ('compliance', 'likelihood', 'completion_percentage', 'COMP_80_100',  80.0, 100.0, 20.0, 4, '80-100% complete'),
  ('compliance', 'likelihood', 'completion_percentage', 'COMP_100',    100.0, 10000.0,  0.0, 5, '100% complete (or greater due to data error)')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Compliance likelihood: userCompletionRate (historical)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'user_completion_rate', 'HIST_0_50',    0.0,  50.0, 85.0, 1, 'Historically poor completion'),
  ('compliance', 'likelihood', 'user_completion_rate', 'HIST_50_70',  50.0,  70.0, 65.0, 2, 'Below average completion'),
  ('compliance', 'likelihood', 'user_completion_rate', 'HIST_70_90',  70.0,  90.0, 40.0, 3, 'Good completion'),
  ('compliance', 'likelihood', 'user_completion_rate', 'HIST_90_100', 90.0, 100.0, 15.0, 4, 'Excellent completion')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Compliance likelihood: lastLoginDays
-- Remove older coarse 30+ bucket so 30/60/90+ buckets do not overlap.
DELETE FROM csod_risk_factor_bucket_metadata
WHERE model_code = 'compliance'
  AND dimension = 'likelihood'
  AND factor_code = 'last_login_days'
  AND bucket_code = 'LOGIN_30_PLUS';

INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'last_login_days', 'LOGIN_0_3',     0.0,   3.0, TRUE, FALSE, 10.0, 1, 'Active recently'),
  ('compliance', 'likelihood', 'last_login_days', 'LOGIN_3_7',     3.0,   7.0, TRUE, FALSE, 25.0, 2, 'Slight inactivity'),
  ('compliance', 'likelihood', 'last_login_days', 'LOGIN_7_14',    7.0,  14.0, TRUE, FALSE, 45.0, 3, 'Moderate inactivity'),
  ('compliance', 'likelihood', 'last_login_days', 'LOGIN_14_30',  14.0,  30.0, TRUE, FALSE, 70.0, 4, 'High inactivity'),
  ('compliance', 'likelihood', 'last_login_days', 'LOGIN_30_60',  30.0,  60.0, TRUE, FALSE, 80.0, 5, 'Very high inactivity (30-60 days)'),
  ('compliance', 'likelihood', 'last_login_days', 'LOGIN_60_90',  60.0,  90.0, TRUE, FALSE, 90.0, 6, 'Extreme inactivity (60-90 days)'),
  ('compliance', 'likelihood', 'last_login_days', 'LOGIN_90_PLUS', 90.0, 10000.0, TRUE, FALSE, 95.0, 7, 'Extreme inactivity (90+ days)')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Compliance likelihood: previousAttempts
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('compliance', 'likelihood', 'previous_attempts', 'ATTEMPTS_0',   0.0, 1.0, 20.0, 1, 'No prior incomplete attempts'),
  ('compliance', 'likelihood', 'previous_attempts', 'ATTEMPTS_1',   1.0, 2.0, 40.0, 2, 'One prior incomplete attempt'),
  ('compliance', 'likelihood', 'previous_attempts', 'ATTEMPTS_2',   2.0, 3.0, 60.0, 3, 'Two prior incomplete attempts'),
  ('compliance', 'likelihood', 'previous_attempts', 'ATTEMPTS_3_PLUS', 3.0, 10000.0, 80.0, 4, 'Three or more prior incomplete attempts')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Compliance impact: estimatedDuration (assume minutes; adjust if your source uses hours)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('compliance', 'impact', 'estimated_duration', 'DUR_0_30',    0.0,   30.0, 30.0, 1, 'Up to 30 minutes'),
  ('compliance', 'impact', 'estimated_duration', 'DUR_30_60',  30.0,   60.0, 45.0, 2, '30-60 minutes'),
  ('compliance', 'impact', 'estimated_duration', 'DUR_60_120', 60.0,  120.0, 60.0, 3, '60-120 minutes'),
  ('compliance', 'impact', 'estimated_duration', 'DUR_120_PLUS', 120.0, 100000.0, 75.0, 4, 'Over 2 hours')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Compliance impact: activity cost (assume cost is in USD; adjust as needed)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('compliance', 'impact', 'activity_cost', 'COST_0',        0.0,    1.0, 20.0, 1, 'Free/near-zero cost'),
  ('compliance', 'impact', 'activity_cost', 'COST_1_100',    1.0,  100.0, 30.0, 2, '$1-$100'),
  ('compliance', 'impact', 'activity_cost', 'COST_100_500', 100.0,  500.0, 50.0, 3, '$100-$500'),
  ('compliance', 'impact', 'activity_cost', 'COST_500_2000', 500.0, 2000.0, 70.0, 4, '$500-$2000'),
  ('compliance', 'impact', 'activity_cost', 'COST_2000_PLUS', 2000.0, 1000000.0, 85.0, 5, '>$2000')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Attrition likelihood: learningEngagementScore (lower => higher likelihood)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'learning_engagement', 'ENG_0_20',   0.0,  20.0, 90.0, 1, 'Very low engagement'),
  ('attrition', 'likelihood', 'learning_engagement', 'ENG_20_40', 20.0,  40.0, 75.0, 2, 'Low engagement'),
  ('attrition', 'likelihood', 'learning_engagement', 'ENG_40_60', 40.0,  60.0, 55.0, 3, 'Medium engagement'),
  ('attrition', 'likelihood', 'learning_engagement', 'ENG_60_80', 60.0,  80.0, 30.0, 4, 'High engagement'),
  ('attrition', 'likelihood', 'learning_engagement', 'ENG_80_100', 80.0, 100.0, 15.0, 5, 'Very high engagement')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Attrition likelihood: courseCompletionRate (derived completion rate over a window; 0-100)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'course_completion_rate', 'CCR_0_60',   0.0,  60.0, TRUE, FALSE, 80.0, 1, 'Low course completion rate'),
  ('attrition', 'likelihood', 'course_completion_rate', 'CCR_60_80', 60.0,  80.0, TRUE, FALSE, 55.0, 2, 'Moderate course completion rate'),
  ('attrition', 'likelihood', 'course_completion_rate', 'CCR_80_95', 80.0,  95.0, TRUE, FALSE, 30.0, 3, 'Good course completion rate'),
  ('attrition', 'likelihood', 'course_completion_rate', 'CCR_95_100', 95.0, 100.0, TRUE, TRUE, 15.0, 4, 'Excellent course completion rate')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Attrition likelihood: completionPercentage (average progress across active assignments; 0-100)
-- Higher completion => lower attrition likelihood (more engaged / following through).
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'completion_percentage', 'COMP_0_20',     0.0,  20.0, TRUE, FALSE, 90.0, 1, '0-20% complete'),
  ('attrition', 'likelihood', 'completion_percentage', 'COMP_20_50',   20.0,  50.0, TRUE, FALSE, 75.0, 2, '20-50% complete'),
  ('attrition', 'likelihood', 'completion_percentage', 'COMP_50_80',   50.0,  80.0, TRUE, FALSE, 50.0, 3, '50-80% complete'),
  ('attrition', 'likelihood', 'completion_percentage', 'COMP_80_100',  80.0, 100.0, TRUE, TRUE,  20.0, 4, '80-100% complete')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Attrition likelihood: daysSinceLastActivityStart (derived days since attemptStartDate/activityStartDate)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'days_since_last_activity_start', 'LAS_0_1',      0.0,    1.0, TRUE, FALSE, 15.0, 1, 'Started within last day'),
  ('attrition', 'likelihood', 'days_since_last_activity_start', 'LAS_1_7',      1.0,    7.0, TRUE, FALSE, 25.0, 2, 'Started within last week'),
  ('attrition', 'likelihood', 'days_since_last_activity_start', 'LAS_7_30',     7.0,   30.0, TRUE, FALSE, 45.0, 3, 'Started 7-30 days ago'),
  ('attrition', 'likelihood', 'days_since_last_activity_start', 'LAS_30_60',   30.0,   60.0, TRUE, FALSE, 65.0, 4, 'Started 30-60 days ago'),
  ('attrition', 'likelihood', 'days_since_last_activity_start', 'LAS_60_90',   60.0,   90.0, TRUE, FALSE, 80.0, 5, 'Started 60-90 days ago'),
  ('attrition', 'likelihood', 'days_since_last_activity_start', 'LAS_90_PLUS', 90.0, 10000.0, TRUE, FALSE, 90.0, 6, 'Started 90+ days ago')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Attrition likelihood: division completion + overdue context buckets (re-using same semantics as compliance; 0-100 percentages)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'division_completion_rate', 'DCR_0_60',     0.0,  60.0, TRUE, FALSE, 70.0, 1, 'Division completion rate <60%'),
  ('attrition', 'likelihood', 'division_completion_rate', 'DCR_60_80',   60.0,  80.0, TRUE, FALSE, 55.0, 2, 'Division completion rate 60-80%'),
  ('attrition', 'likelihood', 'division_completion_rate', 'DCR_80_90',   80.0,  90.0, TRUE, FALSE, 40.0, 3, 'Division completion rate 80-90%'),
  ('attrition', 'likelihood', 'division_completion_rate', 'DCR_90_97',   90.0,  97.0, TRUE, FALSE, 25.0, 4, 'Division completion rate 90-97%'),
  ('attrition', 'likelihood', 'division_completion_rate', 'DCR_97_100',  97.0, 100.0, TRUE, TRUE,  15.0, 5, 'Division completion rate 97-100%'),

  ('attrition', 'likelihood', 'division_overdue_rate', 'DOR_0_1',     0.0,   1.0, TRUE, FALSE, 10.0, 1, 'Division overdue rate <1%'),
  ('attrition', 'likelihood', 'division_overdue_rate', 'DOR_1_5',     1.0,   5.0, TRUE, FALSE, 30.0, 2, 'Division overdue rate 1-5%'),
  ('attrition', 'likelihood', 'division_overdue_rate', 'DOR_5_10',    5.0,  10.0, TRUE, FALSE, 50.0, 3, 'Division overdue rate 5-10%'),
  ('attrition', 'likelihood', 'division_overdue_rate', 'DOR_10_20',  10.0,  20.0, TRUE, FALSE, 70.0, 4, 'Division overdue rate 10-20%'),
  ('attrition', 'likelihood', 'division_overdue_rate', 'DOR_20_PLUS', 20.0, 100.0, TRUE, TRUE,  85.0, 5, 'Division overdue rate 20%+')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO UPDATE SET
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  min_inclusive = EXCLUDED.min_inclusive,
  max_inclusive = EXCLUDED.max_inclusive,
  score = EXCLUDED.score,
  priority_order = EXCLUDED.priority_order,
  description = EXCLUDED.description;

-- Attrition likelihood: complianceCompletionRate (lower => higher likelihood)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'compliance_completion_rate', 'CCR_0_60',  0.0,  60.0, 80.0, 1, 'Low compliance completion'),
  ('attrition', 'likelihood', 'compliance_completion_rate', 'CCR_60_80', 60.0, 80.0, 55.0, 2, 'Moderate compliance completion'),
  ('attrition', 'likelihood', 'compliance_completion_rate', 'CCR_80_95', 80.0, 95.0, 30.0, 3, 'Good compliance completion'),
  ('attrition', 'likelihood', 'compliance_completion_rate', 'CCR_95_100', 95.0, 100.0, 15.0, 4, 'Excellent compliance completion')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Attrition likelihood: lastLoginDays
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'last_login_days', 'LOGIN_0_3',    0.0,   3.0, 10.0, 1, 'Active recently'),
  ('attrition', 'likelihood', 'last_login_days', 'LOGIN_3_7',    3.0,   7.0, 25.0, 2, 'Slight inactivity'),
  ('attrition', 'likelihood', 'last_login_days', 'LOGIN_7_14',   7.0,  14.0, 45.0, 3, 'Moderate inactivity'),
  ('attrition', 'likelihood', 'last_login_days', 'LOGIN_14_30', 14.0,  30.0, 70.0, 4, 'High inactivity'),
  ('attrition', 'likelihood', 'last_login_days', 'LOGIN_30_PLUS', 30.0, 10000.0, 90.0, 5, 'Very high inactivity')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Attrition likelihood: overdueCourseCount
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'overdue_course_count', 'OD_0',     0.0,  1.0, 15.0, 1, 'No overdue courses'),
  ('attrition', 'likelihood', 'overdue_course_count', 'OD_1',     1.0,  2.0, 40.0, 2, '1 overdue course'),
  ('attrition', 'likelihood', 'overdue_course_count', 'OD_2_3',   2.0,  4.0, 60.0, 3, '2-3 overdue courses'),
  ('attrition', 'likelihood', 'overdue_course_count', 'OD_4_6',   4.0,  7.0, 80.0, 4, '4-6 overdue courses'),
  ('attrition', 'likelihood', 'overdue_course_count', 'OD_7_PLUS', 7.0, 10000.0, 95.0, 5, '7+ overdue courses')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Attrition likelihood: managerChangeCount
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('attrition', 'likelihood', 'manager_change_count', 'MC_0',     0.0, 1.0, 20.0, 1, 'No manager changes'),
  ('attrition', 'likelihood', 'manager_change_count', 'MC_1',     1.0, 2.0, 50.0, 2, '1 manager change'),
  ('attrition', 'likelihood', 'manager_change_count', 'MC_2',     2.0, 3.0, 70.0, 3, '2 manager changes'),
  ('attrition', 'likelihood', 'manager_change_count', 'MC_3_PLUS', 3.0, 10000.0, 85.0, 4, '3+ manager changes')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Attrition impact: directReportCount
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('attrition', 'impact', 'direct_report_count', 'DR_0',       0.0,  1.0, 30.0, 1, 'No direct reports'),
  ('attrition', 'impact', 'direct_report_count', 'DR_1_5',     1.0,  6.0, 50.0, 2, '1-5 direct reports'),
  ('attrition', 'impact', 'direct_report_count', 'DR_6_10',    6.0, 11.0, 65.0, 3, '6-10 direct reports'),
  ('attrition', 'impact', 'direct_report_count', 'DR_11_25',  11.0, 26.0, 80.0, 4, '11-25 direct reports'),
  ('attrition', 'impact', 'direct_report_count', 'DR_25_PLUS', 26.0, 10000.0, 90.0, 5, '26+ direct reports')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- Attrition impact: trainingInvestment (USD)
INSERT INTO csod_risk_factor_bucket_metadata
  (model_code, dimension, factor_code, bucket_code, min_value, max_value, score, priority_order, description)
VALUES
  ('attrition', 'impact', 'training_investment', 'TI_0_1000',     0.0,  1000.0, 30.0, 1, 'Up to $1K'),
  ('attrition', 'impact', 'training_investment', 'TI_1000_5000', 1000.0, 5000.0, 50.0, 2, '$1K-$5K'),
  ('attrition', 'impact', 'training_investment', 'TI_5000_10000', 5000.0, 10000.0, 70.0, 3, '$5K-$10K'),
  ('attrition', 'impact', 'training_investment', 'TI_10000_PLUS', 10000.0, 1000000.0, 85.0, 4, '>$10K')
ON CONFLICT (model_code, dimension, factor_code, bucket_code) DO NOTHING;

-- ============================================================================
-- 6) Rules (escalation triggers)
-- ============================================================================
CREATE TABLE IF NOT EXISTS csod_risk_rule_metadata (
    id SERIAL PRIMARY KEY,
    model_code VARCHAR(50) NOT NULL,
    rule_code VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,           -- 'escalation'
    description TEXT,
    condition_type VARCHAR(50) NOT NULL,      -- 'risk_gte' | 'days_until_due_lt'
    condition_value DECIMAL(10,2),
    output_flag_value VARCHAR(50),            -- e.g. 'Yes'
    priority_order INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_code, rule_code)
);

CREATE INDEX IF NOT EXISTS idx_csod_rule_model ON csod_risk_rule_metadata(model_code);
CREATE INDEX IF NOT EXISTS idx_csod_rule_type ON csod_risk_rule_metadata(rule_type);

-- Compliance: "managerEscalation" is triggered when riskScore > 75 OR daysUntilDue < 7
INSERT INTO csod_risk_rule_metadata
  (model_code, rule_code, rule_type, description, condition_type, condition_value, output_flag_value, priority_order)
VALUES
  ('compliance', 'MANAGER_ESCALATE_RISK_GTE_75', 'escalation', 'Escalate to manager when riskScore >= 75', 'risk_gte', 75.0, 'Yes', 1),
  ('compliance', 'MANAGER_ESCALATE_DUE_LT_7',    'escalation', 'Escalate to manager when daysUntilDue < 7', 'days_until_due_lt', 7.0, 'Yes', 2)
ON CONFLICT (model_code, rule_code) DO NOTHING;

-- Attrition: "hrEscalation" is triggered when attritionRiskScore > 75
INSERT INTO csod_risk_rule_metadata
  (model_code, rule_code, rule_type, description, condition_type, condition_value, output_flag_value, priority_order)
VALUES
  ('attrition', 'HR_ESCALATE_RISK_GTE_75', 'escalation', 'Escalate to HR/manager when attritionRiskScore >= 75', 'risk_gte', 75.0, 'Yes', 1)
ON CONFLICT (model_code, rule_code) DO NOTHING;

-- ============================================================================
-- Documentation Comments
-- ============================================================================
COMMENT ON TABLE csod_risk_model_metadata IS 'CSOD risk scoring models (compliance, attrition) and formula metadata';
COMMENT ON TABLE csod_risk_score_band_metadata IS 'Risk category thresholds (Low/Moderate/High/Critical) per CSOD model';
COMMENT ON TABLE csod_risk_factor_metadata IS 'Defines scoring factors and weights for impact and likelihood per model';
COMMENT ON TABLE csod_risk_factor_lookup_metadata IS 'Categorical value to numeric score mappings for CSOD scoring factors';
COMMENT ON TABLE csod_risk_factor_bucket_metadata IS 'Numeric bucket to numeric score mappings for CSOD scoring factors';
COMMENT ON TABLE csod_risk_rule_metadata IS 'Rule metadata for escalation triggers used in CSOD compliance/attrition risk workflows';


