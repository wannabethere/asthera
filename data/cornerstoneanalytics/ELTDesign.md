# ETL/ELT Pipeline Design for Learning Analytics
## Data Ingestion, Transformation, and Quality Frameworks

This document provides comprehensive ETL/ELT pipeline designs to support the 20 analytical use cases and 50 dashboard questions. All pipelines can be implemented using SQL or Analytical Pipes.

---

## 📋 Table of Contents

1. [ETL/ELT Strategy Overview](#strategy-overview)
2. [Core Data Quality Pipelines](#core-data-quality)
3. [Feature Engineering Pipelines](#feature-engineering)
4. [Incremental Load Pipelines](#incremental-loads)
5. [Aggregation & Materialized Views](#aggregations)
6. [Data Validation Pipelines](#data-validation)
7. [Natural Language ETL Questions](#nl-questions)
8. [Pipeline Implementation Examples](#implementation)

---

## 🎯 ETL/ELT Strategy Overview

### Modern ELT Approach
```
Source Systems → Raw Layer → Transform Layer → Analytics Layer → Dashboard Layer
     |              |             |                |                  |
  Extract         Load         Transform        Aggregate         Present
```

### Pipeline Layers

#### **Layer 1: Raw/Landing Zone**
- **Purpose:** Store source data as-is
- **Tables:** `raw_transcript`, `raw_training`, `raw_users`
- **Transformations:** None (exact copy)
- **Frequency:** Real-time or hourly

#### **Layer 2: Cleaned/Standardized**
- **Purpose:** Data quality, type conversion, standardization
- **Tables:** `clean_transcript`, `clean_training`, `clean_users`
- **Transformations:** Quality checks, null handling, deduplication
- **Frequency:** Hourly or daily

#### **Layer 3: Enriched/Enhanced**
- **Purpose:** Feature engineering, derived metrics
- **Tables:** `enriched_transcript`, `user_metrics`, `training_metrics`
- **Transformations:** Calculations, joins, business logic
- **Frequency:** Daily

#### **Layer 4: Analytics/Mart**
- **Purpose:** Pre-aggregated for fast queries
- **Tables:** `fact_completions`, `dim_learner_segments`, `fact_risk_scores`
- **Transformations:** Aggregations, time-series, segmentation
- **Frequency:** Daily or on-demand

---

## 🔍 Core Data Quality Pipelines

### Pipeline 1: Transcript Data Quality & Enrichment

**Source Tables:**
- `transcript_core` (raw)
- `transcript_assignment_core` (raw)
- `training_core` (raw)
- `users_core` (raw)

**Target Table:** `clean_transcript_enriched`

**Pipeline Flow:**
```
TranscriptQualityPipe:
  → FilterPipe.remove_nulls(required_fields=['user_id', 'training_id', 'assigned_dt'])
  → FilterPipe.remove_duplicates(key=['transcript_id'])
  → ValidatePipe.check_referential_integrity(
      foreign_keys={'user_id': 'users_core', 'training_id': 'training_core'}
    )
  → TransformPipe.standardize_dates(
      date_fields=['assigned_dt', 'completed_dt', 'due_dt']
    )
  → TransformPipe.derive_status(
      rules={
        'Overdue': 'due_dt < current_date AND status != "Complete"',
        'At Risk': 'days_until_due < 7 AND status = "In Progress"',
        'On Track': 'status = "In Progress" AND days_until_due >= 7'
      }
    )
  → TransformPipe.calculate_metrics([
      'days_since_assignment': 'current_date - assigned_dt',
      'days_until_due': 'due_dt - current_date',
      'completion_time_days': 'completed_dt - assigned_dt',
      'is_overdue': 'due_dt < current_date AND status != "Complete"',
      'overdue_days': 'CASE WHEN is_overdue THEN current_date - due_dt ELSE 0 END'
    ])
  → ValidatePipe.flag_anomalies(
      rules={
        'negative_completion_time': 'completion_time_days < 0',
        'future_dates': 'assigned_dt > current_date',
        'invalid_status': 'status NOT IN (valid_statuses)'
      }
    )
```

**Output Schema:**
```sql
CREATE TABLE clean_transcript_enriched (
    transcript_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    training_id INT NOT NULL,
    assignment_id INT,
    
    -- Original fields
    assigned_dt DATETIME NOT NULL,
    due_dt DATETIME,
    completed_dt DATETIME,
    status VARCHAR(50),
    score DECIMAL(5,2),
    attempt_number INT,
    
    -- Derived metrics
    days_since_assignment INT,
    days_until_due INT,
    completion_time_days INT,
    is_overdue BOOLEAN,
    overdue_days INT,
    derived_status VARCHAR(50),
    
    -- Quality flags
    has_data_quality_issue BOOLEAN,
    quality_issue_type VARCHAR(100),
    
    -- Audit fields
    processed_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(50),
    
    INDEX idx_user_training (user_id, training_id),
    INDEX idx_dates (assigned_dt, completed_dt),
    INDEX idx_status (status, is_overdue)
);
```

**Natural Language Questions:**
1. "Show me all transcripts with data quality issues from the last load"
2. "What percentage of records had missing required fields today?"
3. "Are there any transcripts with completion times that seem impossible?"
4. "How many records were flagged as anomalies during ETL?"

---

### Pipeline 2: User Dimension Quality & Enrichment

**Source Tables:**
- `users_core` (raw)
- `user_ou_core` (raw)
- `ou_core` (raw)
- `address_core` (raw)
- `user_login_core` (raw)

**Target Table:** `dim_user_enriched`

**Pipeline Flow:**
```
UserEnrichmentPipe:
  → FilterPipe.filter(user_status_id = 'Active' OR recent_activity)
  → JoinPipe.join(user_ou_core, on='user_id', how='left')
  → JoinPipe.join(ou_core, on='ou_id', how='left')
  → JoinPipe.join(address_core, on='address_id', how='left')
  → TransformPipe.calculate_tenure(
      tenure_months = 'MONTHS_BETWEEN(current_date, hire_dt)'
    )
  → TransformPipe.create_tenure_bands([
      '0-3 months', '3-6 months', '6-12 months', 
      '1-2 years', '2-5 years', '5+ years'
    ])
  → TransformPipe.calculate_activity_metrics(
      from_table='user_login_core',
      metrics=['last_login_dt', 'login_count_30d', 'avg_session_minutes']
    )
  → TransformPipe.calculate_geographic_attributes(
      timezone='derive_from_address',
      region='map_country_to_region'
    )
  → ValidatePipe.check_email_format()
  → ValidatePipe.check_mandatory_fields(['user_id', 'email', 'hire_dt'])
```

**Output Schema:**
```sql
CREATE TABLE dim_user_enriched (
    user_id INT PRIMARY KEY,
    
    -- Original fields
    user_name VARCHAR(200),
    email VARCHAR(200),
    hire_dt DATE,
    termination_dt DATE,
    user_status_id INT,
    manager_user_id INT,
    
    -- Organizational
    primary_ou_id INT,
    primary_ou_name VARCHAR(200),
    primary_ou_code VARCHAR(50),
    department_hierarchy VARCHAR(500), -- Full path
    
    -- Geographic
    country_code CHAR(3),
    subdivision1 VARCHAR(60), -- State/Province
    city VARCHAR(70),
    timezone_name VARCHAR(50),
    region VARCHAR(50), -- Derived: EMEA, APAC, Americas
    
    -- Derived metrics
    tenure_months INT,
    tenure_band VARCHAR(50),
    is_manager BOOLEAN,
    direct_reports_count INT,
    
    -- Activity metrics
    last_login_dt DATETIME,
    days_since_last_login INT,
    login_count_30d INT,
    login_count_90d INT,
    avg_session_minutes DECIMAL(10,2),
    is_active_user BOOLEAN, -- Logged in within 90 days
    
    -- Quality flags
    has_data_quality_issue BOOLEAN,
    missing_fields VARCHAR(200),
    
    -- Audit
    effective_from_dt DATETIME,
    effective_to_dt DATETIME,
    is_current BOOLEAN DEFAULT TRUE,
    processed_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_ou (primary_ou_id),
    INDEX idx_manager (manager_user_id),
    INDEX idx_status (user_status_id, is_active_user),
    INDEX idx_geography (country_code, region)
);
```

**Natural Language Questions:**
1. "How many users are missing their primary department assignment?"
2. "Show me users with invalid email formats detected during ETL"
3. "What percentage of active users have logged in within the last 90 days?"
4. "Are there any users with hire dates in the future?"

---

### Pipeline 3: Training/Course Dimension Enrichment

**Source Tables:**
- `training_core` (raw)
- `training_type_core` (raw)
- `training_requirement_tag_core` (raw)
- `transcript_core` (historical completions)

**Target Table:** `dim_training_enriched`

**Pipeline Flow:**
```
TrainingEnrichmentPipe:
  → JoinPipe.join(training_type_core, on='training_type_id')
  → JoinPipe.join(training_requirement_tag_core, on='training_id', how='left')
  → TransformPipe.calculate_historical_metrics(
      from_table='transcript_core',
      lookback_days=365,
      metrics=[
        'total_enrollments',
        'total_completions',
        'historical_completion_rate',
        'avg_completion_days',
        'avg_score',
        'dropout_rate'
      ]
    )
  → TransformPipe.calculate_difficulty_score(
      factors={
        'completion_rate': -0.40,
        'avg_completion_days': 0.20,
        'dropout_rate': 0.25,
        'avg_score': -0.15
      }
    )
  → TransformPipe.assign_difficulty_tier(
      tiers={
        'Beginner': 'difficulty_score < 25',
        'Intermediate': 'difficulty_score 25-50',
        'Advanced': 'difficulty_score 50-75',
        'Expert': 'difficulty_score > 75'
      }
    )
  → TransformPipe.calculate_popularity_rank(
      by='total_enrollments',
      time_window='last_90_days'
    )
  → ValidatePipe.check_required_fields(['training_id', 'training_name'])
  → ValidatePipe.validate_duration_positive()
```

**Output Schema:**
```sql
CREATE TABLE dim_training_enriched (
    training_id INT PRIMARY KEY,
    
    -- Original fields
    training_name VARCHAR(500),
    training_code VARCHAR(100),
    training_type_id INT,
    training_type_name VARCHAR(100),
    estimated_duration DECIMAL(10,2),
    training_hours DECIMAL(10,2),
    
    -- Classification
    is_mandatory BOOLEAN,
    is_certification BOOLEAN,
    certification_valid_months INT,
    delivery_method VARCHAR(50),
    
    -- Historical metrics (rolling 365 days)
    total_enrollments_365d INT,
    total_completions_365d INT,
    historical_completion_rate DECIMAL(5,4),
    avg_completion_days DECIMAL(10,2),
    median_completion_days DECIMAL(10,2),
    std_completion_days DECIMAL(10,2),
    avg_score DECIMAL(5,2),
    dropout_rate DECIMAL(5,4),
    
    -- Derived attributes
    difficulty_score DECIMAL(5,2), -- 0-100
    difficulty_tier VARCHAR(50),
    popularity_rank INT,
    popularity_percentile DECIMAL(5,4),
    
    -- Recent trends (30 days vs 90 days prior)
    enrollment_trend VARCHAR(20), -- 'Increasing', 'Stable', 'Declining'
    enrollment_trend_pct DECIMAL(5,2),
    
    -- Cost (if available)
    cost_per_seat DECIMAL(10,2),
    exam_fee DECIMAL(10,2),
    
    -- Quality indicators
    has_sufficient_history BOOLEAN, -- At least 20 completions
    last_completion_dt DATETIME,
    days_since_last_completion INT,
    
    -- Audit
    metrics_calculated_dt DATETIME,
    processed_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_type (training_type_id),
    INDEX idx_mandatory (is_mandatory),
    INDEX idx_difficulty (difficulty_tier),
    INDEX idx_popularity (popularity_rank)
);
```

**Natural Language Questions:**
1. "Which courses don't have enough historical data for reliable metrics?"
2. "Show me courses where completion rates changed significantly in the last 30 days"
3. "Are there any courses with estimated duration that doesn't match actual average completion time?"
4. "What courses have been inactive (no completions) for over 90 days?"

---

## 🛠️ Feature Engineering Pipelines

### Pipeline 4: User Historical Performance Features

**Purpose:** Calculate user-level historical metrics for risk scoring and segmentation

**Source Tables:**
- `clean_transcript_enriched`
- `dim_user_enriched`

**Target Table:** `user_performance_features`

**Pipeline Flow:**
```
UserFeatureEngineeringPipe:
  → GroupByPipe.group_by(user_id)
  → AggregatePipe.calculate_lifetime_metrics([
      'total_assignments': 'count(*)',
      'total_completions': 'sum(status == "Complete")',
      'lifetime_completion_rate': 'total_completions / total_assignments',
      'total_in_progress': 'sum(status == "In Progress")',
      'total_withdrawn': 'sum(status == "Withdrawn")',
      'total_not_started': 'sum(status IS NULL)'
    ])
  → AggregatePipe.calculate_time_metrics([
      'avg_completion_days': 'mean(completion_time_days WHERE status = "Complete")',
      'median_completion_days': 'median(completion_time_days WHERE status = "Complete")',
      'fastest_completion_days': 'min(completion_time_days WHERE status = "Complete")',
      'slowest_completion_days': 'max(completion_time_days WHERE status = "Complete")'
    ])
  → AggregatePipe.calculate_quality_metrics([
      'avg_score': 'mean(score WHERE status = "Complete")',
      'first_attempt_pass_rate': 'mean(score >= 70 AND attempt_number = 1)',
      'multiple_attempts_rate': 'mean(attempt_number > 1)'
    ])
  → AggregatePipe.calculate_engagement_metrics([
      'courses_per_month': 'count(*) / months_since_first_assignment',
      'days_since_last_activity': 'current_date - max(last_activity_dt)',
      'current_overdue_count': 'sum(is_overdue)',
      'has_current_assignments': 'sum(status IN ["In Progress", "Not Started"]) > 0'
    ])
  → TransformPipe.calculate_rolling_metrics(
      windows=[30, 90, 365],
      metrics=['completion_rate', 'courses_completed', 'avg_score']
    )
  → TransformPipe.calculate_trend_indicators([
      'completion_rate_trend': 'completion_rate_30d - completion_rate_90d',
      'engagement_trend': 'courses_completed_30d vs avg_monthly_rate'
    ])
  → SegmentPipe.assign_learner_persona(
      clustering_features=['completion_rate', 'courses_per_month', 'avg_completion_days']
    )
```

**Output Schema:**
```sql
CREATE TABLE user_performance_features (
    user_id INT PRIMARY KEY,
    
    -- Lifetime metrics
    total_assignments INT,
    total_completions INT,
    lifetime_completion_rate DECIMAL(5,4),
    total_in_progress INT,
    total_withdrawn INT,
    withdrawal_rate DECIMAL(5,4),
    
    -- Time metrics
    avg_completion_days DECIMAL(10,2),
    median_completion_days DECIMAL(10,2),
    completion_time_consistency DECIMAL(10,2), -- Std deviation
    
    -- Quality metrics
    avg_score DECIMAL(5,2),
    first_attempt_pass_rate DECIMAL(5,4),
    multiple_attempts_rate DECIMAL(5,4),
    
    -- Engagement metrics
    courses_per_month DECIMAL(10,2),
    first_assignment_dt DATETIME,
    last_activity_dt DATETIME,
    days_since_last_activity INT,
    current_overdue_count INT,
    has_current_assignments BOOLEAN,
    
    -- Rolling window metrics
    completion_rate_30d DECIMAL(5,4),
    completion_rate_90d DECIMAL(5,4),
    completion_rate_365d DECIMAL(5,4),
    courses_completed_30d INT,
    courses_completed_90d INT,
    courses_completed_365d INT,
    
    -- Trend indicators
    completion_rate_trend VARCHAR(20), -- 'Improving', 'Stable', 'Declining'
    engagement_trend VARCHAR(20),
    
    -- Segmentation
    learner_persona VARCHAR(50), -- 'High Achiever', 'At Risk', etc.
    persona_confidence DECIMAL(5,4),
    
    -- Audit
    features_calculated_dt DATETIME,
    
    INDEX idx_persona (learner_persona),
    INDEX idx_overdue (current_overdue_count),
    INDEX idx_activity (days_since_last_activity)
);
```

**Natural Language Questions:**
1. "Show me users whose completion rate has declined in the last 30 days"
2. "Which users have the most consistent completion times?"
3. "Are there users with high completion rates but low average scores?"
4. "What percentage of users are currently overdue on at least one assignment?"

---

### Pipeline 5: Training Assignment Risk Features

**Purpose:** Pre-calculate risk factors for each active assignment

**Source Tables:**
- `clean_transcript_enriched`
- `user_performance_features`
- `dim_training_enriched`
- `dim_user_enriched`

**Target Table:** `assignment_risk_features`

**Pipeline Flow:**
```
AssignmentRiskFeaturePipe:
  → FilterPipe.filter(status IN ['In Progress', 'Not Started'])
  → JoinPipe.join(user_performance_features, on='user_id')
  → JoinPipe.join(dim_training_enriched, on='training_id')
  → JoinPipe.join(dim_user_enriched, on='user_id')
  → TransformPipe.calculate_time_factors([
      'pct_time_elapsed': '(current_date - assigned_dt) / (due_dt - assigned_dt)',
      'pct_time_remaining': '1 - pct_time_elapsed',
      'days_per_training_hour': 'training_hours / days_until_due'
    ])
  → TransformPipe.calculate_user_factors([
      'user_completion_rate_delta': 'user_completion_rate - avg_org_completion_rate',
      'user_speed_factor': 'user_avg_completion_days / course_avg_completion_days',
      'user_overdue_load': 'user_current_overdue_count'
    ])
  → TransformPipe.calculate_course_factors([
      'course_difficulty_percentile': 'rank_difficulty / total_courses',
      'course_typical_failure_rate': '1 - course_completion_rate'
    ])
  → TransformPipe.calculate_engagement_factors([
      'days_since_user_last_login': 'current_date - last_login_dt',
      'user_has_recent_completions': 'courses_completed_30d > 0',
      'assignment_progress': 'estimated from activity logs if available'
    ])
  → RiskPipe.calculate_composite_risk_score(
      weights={
        'pct_time_elapsed': 0.20,
        'user_completion_rate_delta': 0.25,
        'days_since_user_last_login': 0.15,
        'user_overdue_load': 0.15,
        'course_difficulty_percentile': 0.15,
        'user_has_recent_completions': -0.10
      }
    )
  → SegmentPipe.assign_risk_tier(
      thresholds=[0.3, 0.5, 0.7],
      labels=['Low Risk', 'Medium Risk', 'High Risk', 'Critical Risk']
    )
```

**Output Schema:**
```sql
CREATE TABLE assignment_risk_features (
    assignment_id INT PRIMARY KEY,
    user_id INT,
    training_id INT,
    
    -- Time factors
    assigned_dt DATETIME,
    due_dt DATETIME,
    days_since_assignment INT,
    days_until_due INT,
    pct_time_elapsed DECIMAL(5,4),
    pct_time_remaining DECIMAL(5,4),
    
    -- User factors
    user_completion_rate DECIMAL(5,4),
    user_avg_completion_days DECIMAL(10,2),
    user_completion_rate_delta DECIMAL(6,4), -- vs org average
    user_speed_factor DECIMAL(6,4), -- vs course average
    user_overdue_load INT,
    days_since_user_last_login INT,
    user_has_recent_completions BOOLEAN,
    
    -- Course factors
    course_avg_completion_days DECIMAL(10,2),
    course_completion_rate DECIMAL(5,4),
    course_difficulty_score DECIMAL(5,2),
    course_difficulty_percentile DECIMAL(5,4),
    
    -- Engagement factors
    assignment_progress DECIMAL(5,4), -- 0 to 1 if tracked
    last_activity_on_assignment_dt DATETIME,
    days_since_last_activity INT,
    
    -- Risk scoring
    composite_risk_score DECIMAL(5,4), -- 0 to 1
    risk_tier VARCHAR(50),
    risk_factors_json TEXT, -- Detailed breakdown
    
    -- Predictions
    predicted_completion_probability DECIMAL(5,4),
    predicted_completion_date DATE,
    recommended_intervention VARCHAR(100),
    
    -- Audit
    risk_calculated_dt DATETIME,
    
    INDEX idx_risk_tier (risk_tier),
    INDEX idx_due_date (due_dt),
    INDEX idx_user_training (user_id, training_id),
    INDEX idx_risk_score (composite_risk_score)
);
```

**Natural Language Questions:**
1. "What percentage of assignments in the 'Critical Risk' tier?"
2. "Show me assignments where the user has never logged in since assignment"
3. "Which assignments have less than 25% time remaining and no activity?"
4. "Are there patterns in risk scores by department or training type?"

---

### Pipeline 6: Department Aggregation & Metrics

**Purpose:** Pre-aggregate department-level metrics for dashboards

**Source Tables:**
- `clean_transcript_enriched`
- `dim_user_enriched`
- `dim_training_enriched`

**Target Table:** `dept_training_metrics`

**Pipeline Flow:**
```
DeptAggregationPipe:
  → JoinPipe.join(dim_user_enriched, on='user_id')
  → JoinPipe.join(dim_training_enriched, on='training_id')
  → GroupByPipe.group_by([ou_id, ou_name, metric_date])
  → AggregatePipe.calculate_volume_metrics([
      'active_learners': 'count_distinct(user_id WHERE has_activity)',
      'total_assignments': 'count(*)',
      'total_completions': 'sum(status == "Complete")',
      'total_in_progress': 'sum(status == "In Progress")',
      'total_overdue': 'sum(is_overdue)'
    ])
  → AggregatePipe.calculate_rate_metrics([
      'completion_rate': 'total_completions / total_assignments',
      'overdue_rate': 'total_overdue / total_assignments',
      'on_time_completion_rate': 'sum(completed AND not overdue) / total_completions'
    ])
  → AggregatePipe.calculate_quality_metrics([
      'avg_score': 'mean(score WHERE status = "Complete")',
      'avg_completion_days': 'mean(completion_time_days WHERE status = "Complete")',
      'training_hours_completed': 'sum(training_hours WHERE status = "Complete")'
    ])
  → AggregatePipe.calculate_mandatory_compliance([
      'mandatory_assignments': 'count(WHERE is_mandatory)',
      'mandatory_completions': 'sum(status == "Complete" AND is_mandatory)',
      'mandatory_compliance_rate': 'mandatory_completions / mandatory_assignments',
      'critical_overdue_mandatory': 'sum(is_mandatory AND overdue_days > 30)'
    ])
  → TransformPipe.calculate_vs_organization([
      'completion_rate_vs_org': 'dept_completion_rate - org_avg_completion_rate',
      'rank_by_completion_rate': 'rank() over (order by completion_rate desc)'
    ])
  → TransformPipe.calculate_trend_vs_prior_period([
      'completion_rate_mom_change': 'current_month - prior_month',
      'active_learners_mom_change': 'current_month - prior_month'
    ])
```

**Output Schema:**
```sql
CREATE TABLE dept_training_metrics (
    dept_metric_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ou_id INT,
    ou_name VARCHAR(200),
    metric_date DATE, -- Daily snapshot
    
    -- Volume metrics
    active_learners INT,
    total_employees INT,
    total_assignments INT,
    total_completions INT,
    total_in_progress INT,
    total_not_started INT,
    total_overdue INT,
    
    -- Rate metrics
    completion_rate DECIMAL(5,4),
    overdue_rate DECIMAL(5,4),
    on_time_completion_rate DECIMAL(5,4),
    engagement_rate DECIMAL(5,4), -- active_learners / total_employees
    
    -- Quality metrics
    avg_score DECIMAL(5,2),
    avg_completion_days DECIMAL(10,2),
    training_hours_completed DECIMAL(12,2),
    avg_training_hours_per_employee DECIMAL(10,2),
    
    -- Mandatory compliance
    mandatory_assignments INT,
    mandatory_completions INT,
    mandatory_compliance_rate DECIMAL(5,4),
    critical_overdue_mandatory INT,
    
    -- Comparative metrics
    completion_rate_vs_org DECIMAL(6,4),
    rank_by_completion_rate INT,
    rank_by_compliance_rate INT,
    
    -- Trend metrics (vs prior period)
    completion_rate_mom DECIMAL(6,4),
    completion_rate_mom_change DECIMAL(6,4),
    active_learners_mom INT,
    active_learners_mom_change INT,
    
    -- Audit
    calculated_dt DATETIME,
    
    INDEX idx_ou_date (ou_id, metric_date),
    INDEX idx_date (metric_date),
    INDEX idx_compliance (mandatory_compliance_rate)
);
```

**Natural Language Questions:**
1. "Which departments improved their completion rate the most month-over-month?"
2. "Show me departments below 80% mandatory compliance"
3. "What's the average training hours per employee by department?"
4. "Are there departments with declining active learner counts?"

---

## 🔄 Incremental Load Pipelines

### Pipeline 7: Incremental Transcript Updates

**Purpose:** Efficiently load only changed transcript records

**Source:** `transcript_core` (source system)
**Target:** `clean_transcript_enriched`

**Change Detection Strategy:**
```
IncrementalLoadPipe:
  → FilterPipe.filter(
      _last_touched_dt_utc > last_successful_load_timestamp
    )
  → ValidatePipe.check_data_quality()
  → TransformPipe.apply_business_logic()
  → MergePipe.upsert(
      target='clean_transcript_enriched',
      match_key='transcript_id',
      update_if_exists=True,
      insert_if_new=True
    )
  → LogPipe.log_metrics([
      'records_processed',
      'records_inserted',
      'records_updated',
      'records_failed'
    ])
```

**Implementation SQL:**
```sql
-- Incremental load pattern
MERGE INTO clean_transcript_enriched AS target
USING (
    SELECT 
        t.*,
        -- Derived metrics
        DATEDIFF(day, t.assigned_dt, COALESCE(t.completed_dt, GETDATE())) as completion_time_days,
        CASE 
            WHEN t.due_dt < GETDATE() AND (t.status IS NULL OR t.status != 'Complete')
            THEN 1 ELSE 0 
        END as is_overdue,
        -- Add all enrichment logic here
        GETDATE() as processed_dt
    FROM transcript_core t
    WHERE t._last_touched_dt_utc > :last_load_timestamp
        AND t.transcript_id IS NOT NULL
) AS source
ON target.transcript_id = source.transcript_id
WHEN MATCHED THEN
    UPDATE SET
        target.status = source.status,
        target.completed_dt = source.completed_dt,
        target.score = source.score,
        target.completion_time_days = source.completion_time_days,
        target.is_overdue = source.is_overdue,
        target.processed_dt = source.processed_dt
WHEN NOT MATCHED THEN
    INSERT (transcript_id, user_id, training_id, assigned_dt, ...)
    VALUES (source.transcript_id, source.user_id, source.training_id, ...);
```

**Natural Language Questions:**
1. "How many transcript records were updated in the last ETL run?"
2. "Show me records that changed status from 'In Progress' to 'Complete' today"
3. "What's the average lag time between source update and ETL processing?"
4. "Are there any records that failed validation during the last load?"

---

### Pipeline 8: Slowly Changing Dimension (SCD) for Users

**Purpose:** Track historical changes in user attributes (Type 2 SCD)

**Source:** `users_core`, `user_ou_core`
**Target:** `dim_user_enriched` (with versioning)

**Pipeline Flow:**
```
SCDType2Pipe:
  → ChangeDetectionPipe.detect_changes(
      compare_columns=['ou_id', 'manager_user_id', 'user_status_id']
    )
  → TransformPipe.version_control(
      on_change={
        'expire_current': 'effective_to_dt = current_date - 1, is_current = FALSE',
        'insert_new': 'effective_from_dt = current_date, is_current = TRUE'
      }
    )
  → AuditPipe.log_changes(
      track=['column_changed', 'old_value', 'new_value', 'changed_by', 'changed_dt']
    )
```

**Implementation SQL:**
```sql
-- Detect changes and expire current records
UPDATE dim_user_enriched
SET 
    effective_to_dt = CURRENT_DATE - 1,
    is_current = FALSE
WHERE user_id IN (
    SELECT s.user_id
    FROM users_core s
    JOIN dim_user_enriched t ON s.user_id = t.user_id
    WHERE t.is_current = TRUE
        AND (
            s.primary_ou_id != t.primary_ou_id OR
            s.manager_user_id != t.manager_user_id OR
            s.user_status_id != t.user_status_id
        )
);

-- Insert new versions
INSERT INTO dim_user_enriched (
    user_id, user_name, email, primary_ou_id, manager_user_id,
    effective_from_dt, effective_to_dt, is_current, ...
)
SELECT 
    u.user_id,
    u.user_name,
    u.email,
    uo.ou_id as primary_ou_id,
    u.manager_user_id,
    CURRENT_DATE as effective_from_dt,
    '9999-12-31' as effective_to_dt,
    TRUE as is_current,
    ...
FROM users_core u
LEFT JOIN user_ou_core uo ON u.user_id = uo.user_id AND uo.primary_flag = 1
WHERE NOT EXISTS (
    SELECT 1 FROM dim_user_enriched d
    WHERE d.user_id = u.user_id
        AND d.is_current = TRUE
        AND d.primary_ou_id = uo.ou_id
        AND d.manager_user_id = u.manager_user_id
);
```

**Natural Language Questions:**
1. "How many users changed departments this month?"
2. "Show me users with more than 3 manager changes in the last year"
3. "What percentage of users have historical versions in the dimension?"
4. "Track a specific user's organizational history over time"

---

## 📊 Aggregation & Materialized View Pipelines

### Pipeline 9: Daily Training Metrics Snapshot

**Purpose:** Pre-calculate daily metrics for fast dashboard queries

**Target Table:** `daily_training_metrics`

**Pipeline Flow:**
```
DailySnapshotPipe:
  → SnapshotPipe.take_daily_snapshot(
      snapshot_date=current_date,
      include_all_dimensions=True
    )
  → AggregatePipe.calculate_by_dimensions([
      'date',
      'training_id',
      'ou_id',
      'training_type',
      'delivery_method'
    ])
  → AggregatePipe.calculate_metrics([
      'new_assignments',
      'new_completions',
      'active_learners',
      'overdue_count',
      'avg_score',
      'training_hours_completed'
    ])
  → TransformPipe.calculate_running_totals([
      'ytd_completions',
      'qtd_completions',
      'mtd_completions'
    ])
```

**Output Schema:**
```sql
CREATE TABLE daily_training_metrics (
    metric_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    snapshot_date DATE NOT NULL,
    
    -- Dimensions
    training_id INT,
    training_name VARCHAR(500),
    training_type VARCHAR(100),
    ou_id INT,
    ou_name VARCHAR(200),
    delivery_method VARCHAR(50),
    is_mandatory BOOLEAN,
    
    -- Daily metrics
    new_assignments INT DEFAULT 0,
    new_completions INT DEFAULT 0,
    new_enrollments INT DEFAULT 0,
    active_learners INT DEFAULT 0,
    completions_overdue INT DEFAULT 0,
    completions_on_time INT DEFAULT 0,
    
    -- Quality metrics
    avg_score DECIMAL(5,2),
    avg_completion_days DECIMAL(10,2),
    training_hours_completed DECIMAL(12,2),
    
    -- Running totals
    ytd_completions INT,
    qtd_completions INT,
    mtd_completions INT,
    ytd_training_hours DECIMAL(12,2),
    
    -- Period comparisons
    completions_same_day_last_week INT,
    completions_same_day_last_month INT,
    completions_same_day_last_year INT,
    
    created_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY idx_snapshot (snapshot_date, training_id, ou_id),
    INDEX idx_date (snapshot_date),
    INDEX idx_training (training_id),
    INDEX idx_ou (ou_id)
) PARTITION BY RANGE (YEAR(snapshot_date) * 100 + MONTH(snapshot_date));
```

**Natural Language Questions:**
1. "What were the completion trends for the last 30 days by training type?"
2. "Compare this week's new enrollments to last week by department"
3. "Show me the rolling 7-day average of daily completions"
4. "What's our year-to-date training hours vs. target?"

---

### Pipeline 10: Real-Time Risk Score Materialized View

**Purpose:** Maintain current risk scores for all active assignments

**Pipeline Flow:**
```
RealTimeRiskViewPipe:
  → RefreshPipe.incremental_refresh(
      trigger='on_transcript_update OR hourly',
      refresh_scope='changed_records_only'
    )
  → JoinPipe.join(latest_dimensions)
  → RiskPipe.recalculate_risk_scores()
  → IndexPipe.maintain_indexes()
```

**Implementation:**
```sql
CREATE MATERIALIZED VIEW mv_current_risk_scores AS
SELECT
    ar.assignment_id,
    ar.user_id,
    ar.training_id,
    u.user_name,
    u.email,
    u.primary_ou_name,
    tr.training_name,
    ar.assigned_dt,
    ar.due_dt,
    ar.days_until_due,
    ar.composite_risk_score,
    ar.risk_tier,
    ar.recommended_intervention,
    -- Additional context
    upf.lifetime_completion_rate as user_completion_rate,
    upf.current_overdue_count as user_overdue_count,
    upf.days_since_last_activity as user_days_since_activity,
    ar.risk_calculated_dt
FROM assignment_risk_features ar
JOIN dim_user_enriched u ON ar.user_id = u.user_id
JOIN dim_training_enriched tr ON ar.training_id = tr.training_id
JOIN user_performance_features upf ON ar.user_id = upf.user_id
WHERE u.is_current = TRUE
    AND ar.risk_tier IN ('High Risk', 'Critical Risk')
ORDER BY ar.composite_risk_score DESC, ar.days_until_due ASC;

-- Refresh strategy
REFRESH MATERIALIZED VIEW mv_current_risk_scores;
```

**Natural Language Questions:**
1. "How many assignments are currently in 'Critical Risk' status?"
2. "Show me the top 20 highest risk assignments due this week"
3. "Which users appear most frequently in the high-risk list?"
4. "What's the average risk score by department?"

---

## ✅ Data Validation Pipelines

### Pipeline 11: Comprehensive Data Quality Checks

**Purpose:** Validate data quality across all layers

**Pipeline Flow:**
```
DataQualityPipe:
  → ValidatePipe.check_completeness(
      required_fields_by_table={
        'transcript_core': ['user_id', 'training_id', 'assigned_dt'],
        'users_core': ['user_id', 'email', 'hire_dt'],
        'training_core': ['training_id', 'training_name']
      }
    )
  → ValidatePipe.check_referential_integrity(
      foreign_keys={
        'transcript_core.user_id': 'users_core.user_id',
        'transcript_core.training_id': 'training_core.training_id'
      }
    )
  → ValidatePipe.check_business_rules([
      'completion_time >= 0',
      'score BETWEEN 0 AND 100',
      'due_dt >= assigned_dt',
      'completed_dt >= assigned_dt WHERE status = "Complete"'
    ])
  → ValidatePipe.check_statistical_anomalies(
      columns=['completion_time_days', 'score'],
      method='iqr',
      threshold=3
    )
  → ValidatePipe.check_duplicates(
      unique_keys=['transcript_id', 'user_id + training_id + assigned_dt']
    )
  → LogPipe.log_quality_metrics(
      metrics=['pass_rate', 'fail_count_by_rule', 'anomaly_count']
    )
  → AlertPipe.send_alerts(
      conditions=['pass_rate < 0.95', 'fail_count > threshold']
    )
```

**Output Schema:**
```sql
CREATE TABLE data_quality_log (
    quality_check_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    check_run_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    table_name VARCHAR(100),
    check_type VARCHAR(50), -- 'Completeness', 'Integrity', 'Business Rule', etc.
    check_name VARCHAR(200),
    
    -- Results
    records_checked INT,
    records_passed INT,
    records_failed INT,
    pass_rate DECIMAL(5,4),
    
    -- Details
    failed_record_ids TEXT, -- JSON array
    failure_reasons TEXT, -- JSON object
    sample_failures TEXT, -- First 10 examples
    
    -- Thresholds
    expected_pass_rate DECIMAL(5,4),
    threshold_breached BOOLEAN,
    severity VARCHAR(20), -- 'Info', 'Warning', 'Error', 'Critical'
    
    -- Actions
    alert_sent BOOLEAN,
    alert_recipients VARCHAR(500),
    
    INDEX idx_run_dt (check_run_dt),
    INDEX idx_table_check (table_name, check_type),
    INDEX idx_severity (severity, threshold_breached)
);
```

**Natural Language Questions:**
1. "What data quality issues were detected in today's ETL run?"
2. "Show me the trend of data quality pass rates over the last 30 days"
3. "Which tables have the most referential integrity violations?"
4. "Are there any critical quality issues that need immediate attention?"

---

### Pipeline 12: Anomaly Detection in ETL Process

**Purpose:** Detect unexpected patterns in data volumes and distributions

**Pipeline Flow:**
```
ETLAnomalyDetectionPipe:
  → MonitorPipe.track_volume_metrics([
      'records_per_table',
      'records_per_hour',
      'completions_per_day'
    ])
  → AnomalyPipe.detect_volume_anomalies(
      baseline='historical_average_by_day_of_week',
      threshold=2.5,  # standard deviations
      alert_on=['sudden_spike', 'sudden_drop', 'missing_data']
    )
  → AnomalyPipe.detect_distribution_anomalies(
      columns=['status_distribution', 'completion_time_distribution'],
      method='kl_divergence',
      threshold=0.1
    )
  → AnomalyPipe.detect_temporal_anomalies(
      time_column='assigned_dt',
      expected_pattern='normal_business_hours',
      flag_unusual_times=True
    )
  → AlertPipe.create_alerts(
      priority_rules={
        'no_data_for_6_hours': 'P1',
        'volume_drop_50_pct': 'P2',
        'distribution_shift': 'P3'
      }
    )
```

**Output Schema:**
```sql
CREATE TABLE etl_anomaly_log (
    anomaly_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    detected_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    anomaly_type VARCHAR(50), -- 'Volume', 'Distribution', 'Temporal', 'Pattern'
    
    -- Context
    table_name VARCHAR(100),
    column_name VARCHAR(100),
    metric_name VARCHAR(100),
    
    -- Measurements
    expected_value DECIMAL(18,4),
    actual_value DECIMAL(18,4),
    deviation_pct DECIMAL(8,4),
    z_score DECIMAL(10,4),
    
    -- Classification
    severity VARCHAR(20), -- 'Low', 'Medium', 'High', 'Critical'
    is_true_anomaly BOOLEAN, -- After investigation
    false_positive BOOLEAN,
    
    -- Description
    description TEXT,
    potential_causes TEXT,
    
    -- Actions
    requires_investigation BOOLEAN,
    investigation_status VARCHAR(50),
    resolution_notes TEXT,
    resolved_dt DATETIME,
    
    INDEX idx_detected (detected_dt),
    INDEX idx_severity (severity),
    INDEX idx_requires_investigation (requires_investigation)
);
```

**Natural Language Questions:**
1. "Were there any data volume anomalies detected in the last ETL run?"
2. "Show me all unresolved anomalies from the past week"
3. "What's the false positive rate for our anomaly detection?"
4. "Are there recurring anomalies on specific days or times?"

---

## 💬 Natural Language ETL Questions (50 Questions)

### Data Quality & Validation (Q1-Q10)

**Q1: What percentage of transcript records passed all data quality checks in today's ETL run?**
- **Pipeline:** DataQualityPipe → AggregatePipe
- **Tables:** data_quality_log
- **Metrics:** pass_rate, records_passed, records_failed

**Q2: Show me all records with referential integrity violations detected in the last 24 hours**
- **Pipeline:** ValidatePipe.check_referential_integrity
- **Tables:** data_quality_log, transcript_core
- **Action:** Review and fix orphaned records

**Q3: Are there any users in transcript_core that don't exist in users_core?**
- **Pipeline:** ValidatePipe.check_foreign_keys
- **Tables:** transcript_core, users_core
- **Query Type:** LEFT JOIN with NULL check

**Q4: What's the trend of data quality pass rates over the last 30 days?**
- **Pipeline:** DataQualityPipe → TrendPipe
- **Tables:** data_quality_log
- **Visualization:** Line chart

**Q5: Which data quality rules have the highest failure rates?**
- **Pipeline:** GroupByPipe.group_by(check_name) → RankPipe
- **Tables:** data_quality_log
- **Action:** Prioritize rule improvements

**Q6: Show me sample records that failed the 'completion_time >= 0' business rule**
- **Pipeline:** FilterPipe → ValidatePipe
- **Tables:** clean_transcript_enriched
- **Action:** Data correction

**Q7: Are there duplicate transcript records in the source system?**
- **Pipeline:** ValidatePipe.check_duplicates
- **Tables:** transcript_core
- **Key:** transcript_id or composite key

**Q8: What percentage of users have missing or invalid email addresses?**
- **Pipeline:** ValidatePipe.check_email_format → AggregatePipe
- **Tables:** users_core, dim_user_enriched
- **Action:** Data enrichment

**Q9: How many records were rejected during ETL processing today?**
- **Pipeline:** LogPipe.log_metrics
- **Tables:** etl_run_log
- **Metrics:** records_rejected, rejection_reasons

**Q10: Show me all data quality alerts that were triggered this week**
- **Pipeline:** AlertPipe → FilterPipe
- **Tables:** data_quality_log
- **Filter:** threshold_breached = TRUE

---

### ETL Performance & Monitoring (Q11-Q20)

**Q11: How long did the last full ETL run take for each pipeline?**
- **Pipeline:** MonitorPipe.track_execution_time
- **Tables:** etl_run_log
- **Metrics:** start_time, end_time, duration_minutes

**Q12: What's the average processing time for incremental transcript loads?**
- **Pipeline:** AggregatePipe.mean(duration) → GroupByPipe.group_by(pipeline_name)
- **Tables:** etl_run_log
- **Comparison:** vs SLA targets

**Q13: Are there any ETL pipelines that failed in the last 24 hours?**
- **Pipeline:** FilterPipe.filter(status='Failed')
- **Tables:** etl_run_log
- **Action:** Trigger alerts

**Q14: Show me the volume of records processed by each pipeline today**
- **Pipeline:** GroupByPipe.group_by(pipeline_name) → AggregatePipe.sum(records_processed)
- **Tables:** etl_run_log
- **Visualization:** Bar chart

**Q15: What's the lag time between source system updates and ETL processing?**
- **Pipeline:** TransformPipe.calculate(lag = processed_dt - _last_touched_dt_utc)
- **Tables:** clean_transcript_enriched
- **SLA:** < 1 hour

**Q16: Which ETL steps consume the most processing time?**
- **Pipeline:** GroupByPipe → RankPipe.rank_by(avg_duration)
- **Tables:** etl_step_log
- **Action:** Optimization targets

**Q17: How many times did each pipeline retry before succeeding this week?**
- **Pipeline:** GroupByPipe.group_by(pipeline_name) → AggregatePipe.sum(retry_count)
- **Tables:** etl_run_log
- **Investigation:** Identify flaky pipelines

**Q18: What's the data freshness for each source table?**
- **Pipeline:** AggregatePipe.max(_last_touched_dt_utc) → TransformPipe.calculate(hours_since)
- **Tables:** All source tables
- **Alert:** If > 24 hours

**Q19: Show me ETL pipelines that exceeded their SLA runtime this month**
- **Pipeline:** FilterPipe.filter(duration > sla_threshold)
- **Tables:** etl_run_log
- **Action:** Performance tuning

**Q20: What's the success rate of ETL jobs over the last 90 days?**
- **Pipeline:** AggregatePipe.mean(status == 'Success')
- **Tables:** etl_run_log
- **Visualization:** Success rate trend

---

### Data Transformation & Feature Engineering (Q21-Q30)

**Q21: How many user performance features were recalculated in the last run?**
- **Pipeline:** CountPipe
- **Tables:** user_performance_features
- **Metrics:** Updated vs total records

**Q22: Show me users whose learner persona changed in the last 30 days**
- **Pipeline:** ChangeDetectionPipe → FilterPipe
- **Tables:** user_performance_features (historical)
- **Investigation:** Understand behavior shifts

**Q23: What percentage of assignments have risk scores calculated?**
- **Pipeline:** JoinPipe → AggregatePipe
- **Tables:** transcript_assignment_core, assignment_risk_features
- **Coverage:** Expected 100% for active

**Q24: Are there any training courses missing difficulty scores?**
- **Pipeline:** FilterPipe.filter(difficulty_score IS NULL)
- **Tables:** dim_training_enriched
- **Reason:** Insufficient historical data

**Q25: How many new derived metrics were added to transcripts today?**
- **Pipeline:** ComparisonPipe (today vs yesterday schema)
- **Tables:** clean_transcript_enriched
- **Track:** Schema evolution

**Q26: Show me the distribution of risk tiers across all active assignments**
- **Pipeline:** GroupByPipe.group_by(risk_tier) → AggregatePipe.count
- **Tables:** assignment_risk_features
- **Visualization:** Donut chart

**Q27: Which features have the highest correlation with completion risk?**
- **Pipeline:** CorrelationPipe
- **Tables:** assignment_risk_features
- **Analysis:** Feature importance

**Q28: Are there users with incomplete performance features?**
- **Pipeline:** FilterPipe.filter(NULL IN required_features)
- **Tables:** user_performance_features
- **Action:** Backfill calculation

**Q29: What's the average time to recalculate department metrics?**
- **Pipeline:** AggregatePipe.mean(calculation_time)
- **Tables:** dept_training_metrics, etl_step_log
- **Optimization:** Index tuning

**Q30: Show me features where the calculation logic changed in the last release**
- **Pipeline:** ComparisonPipe (pre-release vs post-release)
- **Tables:** user_performance_features, assignment_risk_features
- **Validation:** Expected changes only

---

### Incremental Loads & Change Detection (Q31-Q40)

**Q31: How many transcript records were inserted vs updated in the last incremental load?**
- **Pipeline:** MergePipe → LogPipe
- **Tables:** etl_run_log
- **Metrics:** inserts_count, updates_count

**Q32: Show me transcripts that changed from 'In Progress' to 'Complete' today**
- **Pipeline:** ChangeDetectionPipe → FilterPipe
- **Tables:** clean_transcript_enriched (with CDC)
- **Business Value:** Daily completion tracking

**Q33: Which users had a department change in the last month?**
- **Pipeline:** SCDType2Pipe → FilterPipe
- **Tables:** dim_user_enriched (historical versions)
- **Query:** Multiple is_current records per user

**Q34: What's the average number of changes per user record per month?**
- **Pipeline:** GroupByPipe.group_by(user_id) → AggregatePipe.count(versions)
- **Tables:** dim_user_enriched
- **Analysis:** SCD churn rate

**Q35: Are there any records that failed to merge during the last upsert?**
- **Pipeline:** MergePipe → ErrorLogPipe
- **Tables:** etl_error_log
- **Investigation:** Merge conflicts

**Q36: Show me the CDC (Change Data Capture) lag for each source table**
- **Pipeline:** TransformPipe.calculate(lag = current_time - _last_touched_dt_utc)
- **Tables:** All source tables
- **SLA:** < 5 minutes for real-time

**Q37: How many records are being processed per minute during peak ETL hours?**
- **Pipeline:** GroupByPipe.group_by(hour, minute) → AggregatePipe
- **Tables:** etl_run_log
- **Capacity:** Planning

**Q38: Which tables have the highest update frequency?**
- **Pipeline:** GroupByPipe.group_by(table_name) → RankPipe
- **Tables:** etl_run_log
- **Action:** Optimize frequently changing tables

**Q39: Show me users who were terminated but still have active assignments**
- **Pipeline:** JoinPipe → FilterPipe
- **Tables:** dim_user_enriched, clean_transcript_enriched
- **Business Rule:** Data cleanup needed

**Q40: What percentage of incremental loads completed without errors this week?**
- **Pipeline:** AggregatePipe.mean(status == 'Success')
- **Tables:** etl_run_log WHERE pipeline_type = 'Incremental'
- **Target:** > 99.5%

---

### Aggregation & Materialized Views (Q41-Q50)

**Q41: When were the department aggregation tables last refreshed?**
- **Pipeline:** AggregatePipe.max(calculated_dt)
- **Tables:** dept_training_metrics
- **SLA:** Daily refresh

**Q42: How much faster are queries on materialized views vs base tables?**
- **Pipeline:** ComparisonPipe (execution times)
- **Tables:** mv_current_risk_scores vs joins
- **Metrics:** Query performance

**Q43: What's the storage size of all materialized views?**
- **Pipeline:** SystemPipe.get_table_sizes
- **Tables:** Information schema
- **Capacity:** Planning

**Q44: Show me which aggregation tables need to be rebuilt due to schema changes**
- **Pipeline:** ValidatePipe.check_schema_compatibility
- **Tables:** All *_metrics tables
- **Action:** Rebuild queue

**Q45: Are there any gaps in the daily training metrics snapshots?**
- **Pipeline:** TimeSeriesPipe.detect_missing_dates
- **Tables:** daily_training_metrics
- **Action:** Backfill missing dates

**Q46: What percentage of dashboard queries hit aggregated tables vs base tables?**
- **Pipeline:** LogPipe.analyze_query_patterns
- **Tables:** query_log
- **Optimization:** Add more aggregations

**Q47: How much data reduction do we achieve with pre-aggregation?**
- **Pipeline:** ComparisonPipe (base table rows vs aggregated rows)
- **Tables:** All *_metrics tables
- **Metrics:** Compression ratio

**Q48: Show me aggregations where the calculation logic drifted from source**
- **Pipeline:** ReconciliationPipe
- **Tables:** Aggregated vs calculated from base
- **Validation:** Data accuracy

**Q49: Which materialized views have the most stale data?**
- **Pipeline:** AggregatePipe.max(age = current_time - last_refresh)
- **Tables:** mv_* tables
- **Action:** Prioritize refresh

**Q50: What's the refresh schedule and completion time for each aggregation table?**
- **Pipeline:** GroupByPipe.group_by(table_name)
- **Tables:** etl_run_log
- **Metrics:** Scheduled time, actual time, duration

---

## 🏗️ Complete ETL Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     SOURCE SYSTEMS                          │
│  LMS Application Database (OLTP)                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Extract (Real-time CDC or Batch)
                  ▼
┌─────────────────────────────────────────────────────────────┐
│               LAYER 1: RAW / LANDING ZONE                   │
│  - raw_transcript_core                                      │
│  - raw_training_core                                        │
│  - raw_users_core                                           │
│  - Exact copy, no transformations                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Data Quality & Standardization Pipes
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            LAYER 2: CLEANED / STANDARDIZED                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ TranscriptQualityPipe                                │   │
│  │  → Remove nulls, duplicates                          │   │
│  │  → Validate referential integrity                    │   │
│  │  → Standardize dates, statuses                       │   │
│  │  → Flag anomalies                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Output: clean_transcript_enriched                          │
│          clean_training_core                                │
│          clean_users_core                                   │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Feature Engineering & Enrichment Pipes
                  ▼
┌─────────────────────────────────────────────────────────────┐
│             LAYER 3: ENRICHED / ENHANCED                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ UserFeatureEngineeringPipe                           │   │
│  │  → Calculate historical metrics                      │   │
│  │  → Derive engagement features                        │   │
│  │  → Assign learner personas                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ TrainingEnrichmentPipe                               │   │
│  │  → Calculate difficulty scores                       │   │
│  │  → Popularity rankings                               │   │
│  │  → Historical completion rates                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ AssignmentRiskFeaturePipe                            │   │
│  │  → Calculate risk scores                             │   │
│  │  → Assign risk tiers                                 │   │
│  │  → Generate recommendations                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Output: user_performance_features                          │
│          dim_training_enriched                              │
│          assignment_risk_features                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Aggregation & Analytics Pipes
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              LAYER 4: ANALYTICS / MART                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ DeptAggregationPipe                                  │   │
│  │  → Department metrics                                │   │
│  │  → Compliance tracking                               │   │
│  │  → Trend calculation                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ DailySnapshotPipe                                    │   │
│  │  → Daily training metrics                            │   │
│  │  → Running totals                                    │   │
│  │  → YTD/QTD/MTD calculations                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Output: dept_training_metrics                              │
│          daily_training_metrics                             │
│          mv_current_risk_scores (materialized view)         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Dashboard & Reporting Layer
                  ▼
┌─────────────────────────────────────────────────────────────┐
│               LAYER 5: PRESENTATION                         │
│  - BI Tools (Tableau, Power BI, Looker)                    │
│  - Dashboard Queries (50 Questions)                         │
│  - Analytics Use Cases (20 Use Cases)                       │
│  - Real-time Alerts & Notifications                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 ETL Pipeline Orchestration Schedule

### Recommended Schedule

| Pipeline | Frequency | Duration | Dependencies | Priority |
|----------|-----------|----------|--------------|----------|
| **Raw Layer Extraction** | Every 1 hour | 5-10 min | Source systems | P1 |
| **Data Quality Checks** | Every 1 hour | 5-10 min | Raw layer | P1 |
| **Transcript Enrichment** | Every 1 hour | 10-15 min | Quality checks | P1 |
| **User Dimension (SCD)** | Daily at 2 AM | 15-30 min | Raw users | P2 |
| **Training Dimension** | Daily at 3 AM | 15-30 min | Historical transcripts | P2 |
| **User Performance Features** | Daily at 4 AM | 30-45 min | Clean transcripts | P2 |
| **Assignment Risk Scores** | Every 4 hours | 20-30 min | User features, training dim | P1 |
| **Department Aggregations** | Daily at 5 AM | 15-20 min | Clean transcripts, user dim | P2 |
| **Daily Metrics Snapshot** | Daily at 6 AM | 10-15 min | All dimensions | P2 |
| **Materialized View Refresh** | Every 2 hours | 5-10 min | Risk features | P1 |

**Total Daily ETL Window:** ~6 hours (midnight to 6 AM)  
**Critical Path:** Raw → Quality → Enrichment → Risk Scores → Dashboards

---

## 🎯 Implementation Priorities

### Phase 1: Foundation (Weeks 1-2)
1. ✅ Set up raw layer extraction
2. ✅ Implement core data quality checks
3. ✅ Build transcript enrichment pipeline
4. ✅ Create user dimension (basic, no SCD yet)
5. ✅ Deploy incremental load pattern

### Phase 2: Features (Weeks 3-4)
1. ✅ User performance feature engineering
2. ✅ Training enrichment with difficulty scores
3. ✅ Assignment risk scoring
4. ✅ Implement SCD Type 2 for users

### Phase 3: Aggregations (Weeks 5-6)
1. ✅ Department metrics aggregation
2. ✅ Daily training metrics snapshots
3. ✅ Materialized views for dashboards
4. ✅ Set up orchestration schedules

### Phase 4: Advanced (Weeks 7-8)
1. ✅ Anomaly detection in ETL
2. ✅ Advanced validation rules
3. ✅ Performance optimization
4. ✅ Monitoring and alerting

---

## 💡 Best Practices

### 1. Idempotency
All ETL pipelines should be idempotent - running the same pipeline multiple times should produce the same result.

```sql
-- Example: Idempotent daily snapshot
DELETE FROM daily_training_metrics WHERE snapshot_date = CURRENT_DATE;

INSERT INTO daily_training_metrics (...)
SELECT ... FROM clean_transcript_enriched
WHERE CAST(completed_dt AS DATE) = CURRENT_DATE;
```

### 2. Error Handling
Implement comprehensive error handling with retry logic.

```
ErrorHandlingPipe:
  → TryPipe.execute(main_pipeline)
  → CatchPipe.on_error(
      log_error=True,
      retry_count=3,
      retry_delay_seconds=60,
      on_final_failure='send_alert'
    )
```

### 3. Data Lineage
Track data lineage for audit and troubleshooting.

```sql
CREATE TABLE data_lineage (
    lineage_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_table VARCHAR(100),
    source_record_id BIGINT,
    target_table VARCHAR(100),
    target_record_id BIGINT,
    transformation_applied VARCHAR(200),
    pipeline_name VARCHAR(100),
    processed_dt DATETIME,
    INDEX idx_source (source_table, source_record_id),
    INDEX idx_target (target_table, target_record_id)
);
```

### 4. Monitoring Dashboards
Create ETL monitoring dashboards tracking:
- Pipeline success rates
- Data quality trends
- Processing times
- Data volumes
- Anomaly detection results

---

This ETL/ELT pipeline documentation provides a complete framework for building robust data ingestion and transformation processes to support all 20 analytical use cases and 50 dashboard questions. All pipelines can be implemented using SQL or the Analytical Pipe framework.