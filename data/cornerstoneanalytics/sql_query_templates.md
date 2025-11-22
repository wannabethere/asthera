# SQL Query Templates for Learning Analytics Use Cases
## Ready-to-Use Query Patterns

This document provides SQL query templates for common patterns across all 20 analytical use cases.

---

## 🔧 Common Table Expressions (CTEs) - Building Blocks

### 1. Active Learners Base CTE
```sql
WITH active_learners AS (
    SELECT DISTINCT
        u.user_id,
        u.user_name,
        u.email,
        u.user_status_id,
        MAX(t.last_activity_dt) as last_activity_dt
    FROM users_core u
    JOIN transcript_core t ON u.user_id = t.user_id
    WHERE u.user_status_id = 1  -- Active status
        AND t.last_activity_dt >= DATEADD(month, -3, GETDATE())
    GROUP BY u.user_id, u.user_name, u.email, u.user_status_id
)
```

### 2. User Department Assignment CTE
```sql
WITH user_departments AS (
    SELECT
        uo.user_id,
        uo.ou_id,
        o.ou_name,
        o.ou_code,
        uo.primary_flag
    FROM user_ou_core uo
    JOIN ou_core o ON uo.ou_id = o.ou_id
    WHERE uo.primary_flag = 1  -- Primary department only
)
```

### 3. Training Assignments with Status CTE
```sql
WITH assignments_with_status AS (
    SELECT
        ta.assignment_id,
        ta.user_id,
        ta.training_id,
        ta.assigned_dt,
        ta.due_dt,
        t.status,
        t.completed_dt,
        t.score,
        DATEDIFF(day, ta.assigned_dt, COALESCE(t.completed_dt, GETDATE())) as days_to_complete,
        CASE 
            WHEN ta.due_dt < GETDATE() AND (t.status IS NULL OR t.status != 'Complete')
            THEN 1 ELSE 0 
        END as is_overdue,
        DATEDIFF(day, ta.due_dt, GETDATE()) as days_overdue
    FROM transcript_assignment_core ta
    LEFT JOIN transcript_core t ON ta.assignment_id = t.transcript_id
)
```

### 4. Completion Time Baseline CTE
```sql
WITH completion_baseline AS (
    SELECT
        tr.training_id,
        tr.training_name,
        AVG(DATEDIFF(day, t.assigned_dt, t.completed_dt)) as avg_completion_days,
        STDEV(DATEDIFF(day, t.assigned_dt, t.completed_dt)) as std_completion_days,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY DATEDIFF(day, t.assigned_dt, t.completed_dt)) 
            as median_completion_days,
        COUNT(*) as completion_count
    FROM transcript_core t
    JOIN training_core tr ON t.training_id = tr.training_id
    WHERE t.status = 'Complete'
        AND DATEDIFF(day, t.assigned_dt, t.completed_dt) > 0
    GROUP BY tr.training_id, tr.training_name
    HAVING COUNT(*) >= 20  -- Minimum sample size
)
```

---

## 📈 TREND ANALYSIS QUERIES

### Use Case 1: Course Enrollment Trends by Department

```sql
-- Monthly enrollment trends by department
WITH monthly_enrollments AS (
    SELECT
        DATEPART(year, ta.assigned_dt) as year,
        DATEPART(month, ta.assigned_dt) as month,
        DATEFROMPARTS(DATEPART(year, ta.assigned_dt), DATEPART(month, ta.assigned_dt), 1) as month_date,
        o.ou_name,
        o.ou_id,
        COUNT(ta.assignment_id) as enrollment_count
    FROM transcript_assignment_core ta
    JOIN user_ou_core uo ON ta.user_id = uo.user_id
    JOIN ou_core o ON uo.ou_id = o.ou_id
    WHERE ta.assigned_dt >= DATEADD(month, -12, GETDATE())
        AND uo.primary_flag = 1
    GROUP BY 
        DATEPART(year, ta.assigned_dt),
        DATEPART(month, ta.assigned_dt),
        DATEFROMPARTS(DATEPART(year, ta.assigned_dt), DATEPART(month, ta.assigned_dt), 1),
        o.ou_name,
        o.ou_id
),
trend_calculation AS (
    SELECT
        ou_name,
        month_date,
        enrollment_count,
        AVG(enrollment_count) OVER (
            PARTITION BY ou_name 
            ORDER BY month_date 
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) as moving_avg_3m,
        LAG(enrollment_count, 1) OVER (PARTITION BY ou_name ORDER BY month_date) as prev_month,
        LAG(enrollment_count, 12) OVER (PARTITION BY ou_name ORDER BY month_date) as same_month_last_year
    FROM monthly_enrollments
)
SELECT
    ou_name,
    month_date,
    enrollment_count,
    moving_avg_3m,
    prev_month,
    same_month_last_year,
    CASE 
        WHEN prev_month IS NOT NULL 
        THEN ROUND(100.0 * (enrollment_count - prev_month) / prev_month, 2)
        ELSE NULL 
    END as mom_pct_change,
    CASE 
        WHEN same_month_last_year IS NOT NULL 
        THEN ROUND(100.0 * (enrollment_count - same_month_last_year) / same_month_last_year, 2)
        ELSE NULL 
    END as yoy_pct_change
FROM trend_calculation
ORDER BY ou_name, month_date;
```

### Use Case 6: Training Assignment Response Time

```sql
-- Response time analysis with trend detection
WITH response_time_data AS (
    SELECT
        ta.assignment_id,
        ta.user_id,
        ta.assigned_dt,
        t.first_activity_dt,
        DATEDIFF(day, ta.assigned_dt, t.first_activity_dt) as response_time_days,
        DATEFROMPARTS(
            DATEPART(year, ta.assigned_dt),
            DATEPART(month, ta.assigned_dt), 
            1
        ) as assigned_month
    FROM transcript_assignment_core ta
    LEFT JOIN transcript_core t ON ta.assignment_id = t.transcript_id
    WHERE ta.assigned_dt >= DATEADD(month, -12, GETDATE())
        AND DATEDIFF(day, ta.assigned_dt, t.first_activity_dt) >= 0
),
monthly_stats AS (
    SELECT
        assigned_month,
        COUNT(*) as assignment_count,
        AVG(response_time_days) as avg_response_days,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_days) as median_response_days,
        STDEV(response_time_days) as std_response_days,
        MIN(response_time_days) as min_response_days,
        MAX(response_time_days) as max_response_days
    FROM response_time_data
    GROUP BY assigned_month
)
SELECT
    assigned_month,
    assignment_count,
    avg_response_days,
    median_response_days,
    std_response_days,
    AVG(median_response_days) OVER (
        ORDER BY assigned_month 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) as moving_median_3m,
    LAG(median_response_days, 1) OVER (ORDER BY assigned_month) as prev_month_median,
    CASE 
        WHEN LAG(median_response_days, 1) OVER (ORDER BY assigned_month) IS NOT NULL
        THEN ROUND(100.0 * (median_response_days - LAG(median_response_days, 1) OVER (ORDER BY assigned_month)) 
            / LAG(median_response_days, 1) OVER (ORDER BY assigned_month), 2)
        ELSE NULL
    END as pct_change_from_prev
FROM monthly_stats
ORDER BY assigned_month;
```

---

## ⚠️ RISK SCORING QUERIES

### Use Case 2: Predicting Course Non-Completion Risk

```sql
-- Calculate risk features for active assignments
WITH user_history AS (
    SELECT
        user_id,
        COUNT(*) as total_assignments,
        SUM(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END) as completed_count,
        CAST(SUM(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END) AS FLOAT) / 
            NULLIF(COUNT(*), 0) as historical_completion_rate,
        AVG(CASE 
            WHEN status = 'Complete' 
            THEN DATEDIFF(day, assigned_dt, completed_dt) 
        END) as avg_days_to_complete
    FROM transcript_core
    WHERE assigned_dt < DATEADD(month, -3, GETDATE())  -- Historical data
    GROUP BY user_id
),
current_assignments AS (
    SELECT
        ta.assignment_id,
        ta.user_id,
        ta.training_id,
        ta.assigned_dt,
        ta.due_dt,
        tr.training_name,
        tr.estimated_duration,
        DATEDIFF(day, ta.assigned_dt, GETDATE()) as days_since_assignment,
        DATEDIFF(day, GETDATE(), ta.due_dt) as days_until_due,
        u.last_login_dt,
        DATEDIFF(day, u.last_login_dt, GETDATE()) as days_since_last_login
    FROM transcript_assignment_core ta
    JOIN training_core tr ON ta.training_id = tr.training_id
    JOIN users_core u ON ta.user_id = u.user_id
    LEFT JOIN transcript_core t ON ta.assignment_id = t.transcript_id
    WHERE (t.status IS NULL OR t.status = 'In Progress')
        AND u.user_status_id = 1  -- Active users only
),
risk_features AS (
    SELECT
        ca.*,
        COALESCE(uh.historical_completion_rate, 0.5) as historical_completion_rate,
        COALESCE(uh.avg_days_to_complete, 30) as avg_historical_completion_days,
        COALESCE(uh.completed_count, 0) as previous_completions,
        -- Risk factors
        CASE WHEN ca.days_since_assignment > 30 THEN 1 ELSE 0 END as long_inactive_flag,
        CASE WHEN ca.days_until_due < 7 THEN 1 ELSE 0 END as deadline_approaching_flag,
        CASE WHEN ca.days_since_last_login > 14 THEN 1 ELSE 0 END as disengaged_flag
    FROM current_assignments ca
    LEFT JOIN user_history uh ON ca.user_id = uh.user_id
)
SELECT
    assignment_id,
    user_id,
    training_name,
    days_since_assignment,
    days_until_due,
    historical_completion_rate,
    -- Simple rule-based risk score (0-100)
    CAST(
        (30 * (1 - historical_completion_rate)) +  -- 30 points for low completion history
        (20 * long_inactive_flag) +                 -- 20 points if long inactive
        (25 * deadline_approaching_flag) +          -- 25 points if deadline near
        (25 * disengaged_flag)                      -- 25 points if disengaged
    AS INT) as risk_score,
    CASE
        WHEN (
            (30 * (1 - historical_completion_rate)) +
            (20 * long_inactive_flag) +
            (25 * deadline_approaching_flag) +
            (25 * disengaged_flag)
        ) >= 70 THEN 'High Risk'
        WHEN (
            (30 * (1 - historical_completion_rate)) +
            (20 * long_inactive_flag) +
            (25 * deadline_approaching_flag) +
            (25 * disengaged_flag)
        ) >= 30 THEN 'Medium Risk'
        ELSE 'Low Risk'
    END as risk_category
FROM risk_features
ORDER BY risk_score DESC;
```

### Use Case 7: Department Compliance Risk

```sql
-- Department compliance risk scoring
WITH department_compliance AS (
    SELECT
        o.ou_id,
        o.ou_name,
        COUNT(DISTINCT ta.user_id) as total_users,
        COUNT(ta.assignment_id) as total_assignments,
        SUM(CASE WHEN t.status = 'Complete' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN t.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
        SUM(CASE 
            WHEN ta.due_dt < GETDATE() AND (t.status IS NULL OR t.status != 'Complete')
            THEN 1 ELSE 0 
        END) as overdue,
        SUM(CASE 
            WHEN ta.due_dt < GETDATE() - 30 AND (t.status IS NULL OR t.status != 'Complete')
            THEN 1 ELSE 0 
        END) as critical_overdue,
        AVG(CASE 
            WHEN ta.due_dt < GETDATE() AND (t.status IS NULL OR t.status != 'Complete')
            THEN DATEDIFF(day, ta.due_dt, GETDATE())
            ELSE 0
        END) as avg_days_overdue
    FROM user_ou_core uo
    JOIN ou_core o ON uo.ou_id = o.ou_id
    JOIN transcript_assignment_core ta ON uo.user_id = ta.user_id
    JOIN training_requirement_tag_core rt ON ta.training_id = rt.training_id
    LEFT JOIN transcript_core t ON ta.assignment_id = t.transcript_id
    WHERE uo.primary_flag = 1
        AND rt.is_mandatory = 1
    GROUP BY o.ou_id, o.ou_name
)
SELECT
    ou_name,
    total_users,
    total_assignments,
    completed,
    in_progress,
    overdue,
    critical_overdue,
    ROUND(100.0 * completed / NULLIF(total_assignments, 0), 2) as completion_rate,
    ROUND(100.0 * overdue / NULLIF(total_assignments, 0), 2) as overdue_rate,
    ROUND(avg_days_overdue, 1) as avg_days_overdue,
    -- Risk score calculation (0-100)
    CAST(
        (40 * (1 - (completed / NULLIF(CAST(total_assignments AS FLOAT), 0)))) +  -- Completion rate weight
        (30 * (overdue / NULLIF(CAST(total_assignments AS FLOAT), 0))) +           -- Overdue rate weight
        (20 * (critical_overdue / NULLIF(CAST(overdue AS FLOAT), 0))) +            -- Critical overdue weight
        (10 * LEAST(avg_days_overdue / 60.0, 1))                                   -- Days overdue weight
    AS INT) as compliance_risk_score,
    CASE
        WHEN (40 * (1 - (completed / NULLIF(CAST(total_assignments AS FLOAT), 0))) +
              30 * (overdue / NULLIF(CAST(total_assignments AS FLOAT), 0)) +
              20 * (critical_overdue / NULLIF(CAST(overdue AS FLOAT), 0)) +
              10 * LEAST(avg_days_overdue / 60.0, 1)) >= 75 THEN 'Critical'
        WHEN (40 * (1 - (completed / NULLIF(CAST(total_assignments AS FLOAT), 0))) +
              30 * (overdue / NULLIF(CAST(total_assignments AS FLOAT), 0)) +
              20 * (critical_overdue / NULLIF(CAST(overdue AS FLOAT), 0)) +
              10 * LEAST(avg_days_overdue / 60.0, 1)) >= 50 THEN 'High Risk'
        WHEN (40 * (1 - (completed / NULLIF(CAST(total_assignments AS FLOAT), 0))) +
              30 * (overdue / NULLIF(CAST(total_assignments AS FLOAT), 0)) +
              20 * (critical_overdue / NULLIF(CAST(overdue AS FLOAT), 0)) +
              10 * LEAST(avg_days_overdue / 60.0, 1)) >= 25 THEN 'Medium Risk'
        ELSE 'Low Risk'
    END as risk_level
FROM department_compliance
ORDER BY compliance_risk_score DESC;
```

---

## 🔍 ANOMALY DETECTION QUERIES

### Use Case 3: Unusual Completion Patterns

```sql
-- Detect anomalous completion times using IQR method
WITH completion_data AS (
    SELECT
        t.transcript_id,
        t.user_id,
        t.training_id,
        tr.training_name,
        DATEDIFF(day, t.assigned_dt, t.completed_dt) as completion_time_days,
        tr.estimated_duration
    FROM transcript_core t
    JOIN training_core tr ON t.training_id = tr.training_id
    WHERE t.status = 'Complete'
        AND DATEDIFF(day, t.assigned_dt, t.completed_dt) > 0
),
training_statistics AS (
    SELECT
        training_id,
        training_name,
        AVG(completion_time_days) as mean_days,
        STDEV(completion_time_days) as std_days,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY completion_time_days) as q1,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY completion_time_days) as median,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY completion_time_days) as q3,
        COUNT(*) as sample_size
    FROM completion_data
    GROUP BY training_id, training_name
    HAVING COUNT(*) >= 30  -- Need sufficient sample
),
iqr_bounds AS (
    SELECT
        *,
        q3 - q1 as iqr,
        q1 - (1.5 * (q3 - q1)) as lower_bound,
        q3 + (1.5 * (q3 - q1)) as upper_bound
    FROM training_statistics
),
anomalies AS (
    SELECT
        cd.transcript_id,
        cd.user_id,
        cd.training_id,
        cd.training_name,
        cd.completion_time_days,
        cd.estimated_duration,
        ts.mean_days,
        ts.median,
        ts.std_days,
        ib.lower_bound,
        ib.upper_bound,
        CASE
            WHEN cd.completion_time_days < ib.lower_bound THEN 'Unusually Fast'
            WHEN cd.completion_time_days > ib.upper_bound THEN 'Unusually Slow'
            ELSE 'Normal'
        END as anomaly_type,
        ABS(cd.completion_time_days - ts.median) / NULLIF(ts.std_days, 0) as z_score
    FROM completion_data cd
    JOIN training_statistics ts ON cd.training_id = ts.training_id
    JOIN iqr_bounds ib ON cd.training_id = ib.training_id
    WHERE cd.completion_time_days < ib.lower_bound 
        OR cd.completion_time_days > ib.upper_bound
)
SELECT
    transcript_id,
    user_id,
    training_name,
    completion_time_days,
    estimated_duration,
    ROUND(median, 1) as typical_median_days,
    anomaly_type,
    ROUND(z_score, 2) as z_score,
    CASE
        WHEN ABS(z_score) >= 3 THEN 'Severe Anomaly'
        WHEN ABS(z_score) >= 2 THEN 'Moderate Anomaly'
        ELSE 'Mild Anomaly'
    END as severity
FROM anomalies
ORDER BY ABS(z_score) DESC;
```

### Use Case 8: Sudden Enrollment Spikes

```sql
-- Detect enrollment spikes using moving average and standard deviation
WITH daily_enrollments AS (
    SELECT
        CAST(assigned_dt AS DATE) as enrollment_date,
        training_id,
        COUNT(assignment_id) as enrollment_count
    FROM transcript_assignment_core
    WHERE assigned_dt >= DATEADD(day, -90, GETDATE())
    GROUP BY CAST(assigned_dt AS DATE), training_id
),
rolling_stats AS (
    SELECT
        enrollment_date,
        training_id,
        enrollment_count,
        AVG(enrollment_count) OVER (
            PARTITION BY training_id 
            ORDER BY enrollment_date 
            ROWS BETWEEN 13 PRECEDING AND 1 PRECEDING
        ) as rolling_avg_14d,
        STDEV(enrollment_count) OVER (
            PARTITION BY training_id 
            ORDER BY enrollment_date 
            ROWS BETWEEN 13 PRECEDING AND 1 PRECEDING
        ) as rolling_std_14d
    FROM daily_enrollments
),
anomaly_detection AS (
    SELECT
        rs.enrollment_date,
        rs.training_id,
        tr.training_name,
        rs.enrollment_count,
        rs.rolling_avg_14d,
        rs.rolling_std_14d,
        rs.rolling_avg_14d + (3 * rs.rolling_std_14d) as upper_threshold,
        rs.rolling_avg_14d - (3 * rs.rolling_std_14d) as lower_threshold,
        (rs.enrollment_count - rs.rolling_avg_14d) / NULLIF(rs.rolling_std_14d, 0) as z_score
    FROM rolling_stats rs
    JOIN training_core tr ON rs.training_id = tr.training_id
    WHERE rs.rolling_avg_14d IS NOT NULL
        AND rs.rolling_std_14d > 0
)
SELECT
    enrollment_date,
    training_name,
    enrollment_count,
    ROUND(rolling_avg_14d, 1) as expected_enrollments,
    ROUND(rolling_std_14d, 1) as typical_variation,
    ROUND(z_score, 2) as z_score,
    CASE
        WHEN enrollment_count > upper_threshold THEN 'Unusual Spike'
        WHEN enrollment_count < lower_threshold THEN 'Unusual Drop'
        ELSE 'Normal'
    END as anomaly_type,
    CASE
        WHEN ABS(z_score) >= 4 THEN 'Critical'
        WHEN ABS(z_score) >= 3 THEN 'High'
        WHEN ABS(z_score) >= 2 THEN 'Moderate'
        ELSE 'Low'
    END as severity
FROM anomaly_detection
WHERE ABS(z_score) >= 2  -- Flag moderate or higher anomalies
ORDER BY ABS(z_score) DESC, enrollment_date DESC;
```

---

## 👥 SEGMENTATION QUERIES

### Use Case 4: Learner Persona Development

```sql
-- Calculate learner features for clustering
WITH learner_metrics AS (
    SELECT
        t.user_id,
        u.user_name,
        u.email,
        COUNT(*) as total_courses,
        SUM(CASE WHEN t.status = 'Complete' THEN 1 ELSE 0 END) as completed_courses,
        SUM(CASE WHEN t.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress_courses,
        SUM(CASE WHEN t.status = 'Withdrawn' THEN 1 ELSE 0 END) as withdrawn_courses,
        CAST(SUM(CASE WHEN t.status = 'Complete' THEN 1 ELSE 0 END) AS FLOAT) / 
            NULLIF(COUNT(*), 0) as completion_rate,
        AVG(CASE 
            WHEN t.status = 'Complete' 
            THEN DATEDIFF(day, t.assigned_dt, t.completed_dt) 
        END) as avg_days_to_complete,
        AVG(CASE WHEN t.status = 'Complete' THEN t.score END) as avg_score,
        DATEDIFF(day, MAX(t.last_activity_dt), GETDATE()) as days_since_last_activity,
        COUNT(*) / NULLIF(
            DATEDIFF(month, MIN(t.assigned_dt), GETDATE()), 0
        ) as courses_per_month
    FROM transcript_core t
    JOIN users_core u ON t.user_id = u.user_id
    WHERE u.user_status_id = 1  -- Active users
        AND t.assigned_dt >= DATEADD(year, -1, GETDATE())
    GROUP BY t.user_id, u.user_name, u.email
    HAVING COUNT(*) >= 3  -- Need minimum activity
),
normalized_scores AS (
    SELECT
        user_id,
        user_name,
        email,
        completed_courses,
        completion_rate,
        avg_days_to_complete,
        avg_score,
        days_since_last_activity,
        courses_per_month,
        -- Normalize metrics for comparison (simple min-max normalization)
        (completion_rate - MIN(completion_rate) OVER ()) / 
            NULLIF(MAX(completion_rate) OVER () - MIN(completion_rate) OVER (), 0) as norm_completion_rate,
        (avg_days_to_complete - MIN(avg_days_to_complete) OVER ()) / 
            NULLIF(MAX(avg_days_to_complete) OVER () - MIN(avg_days_to_complete) OVER (), 0) as norm_speed,
        (courses_per_month - MIN(courses_per_month) OVER ()) / 
            NULLIF(MAX(courses_per_month) OVER () - MIN(courses_per_month) OVER (), 0) as norm_frequency
    FROM learner_metrics
),
segment_assignment AS (
    SELECT
        *,
        -- Simple rule-based segmentation (to be replaced with ML clustering)
        CASE
            WHEN completion_rate >= 0.8 AND courses_per_month >= 1.5 
                THEN 'High Achiever'
            WHEN completion_rate >= 0.8 AND courses_per_month < 1.5 
                THEN 'Steady Performer'
            WHEN completion_rate < 0.5 AND days_since_last_activity > 30 
                THEN 'At Risk'
            WHEN completion_rate < 0.5 
                THEN 'Struggling Learner'
            WHEN avg_days_to_complete < (SELECT PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY avg_days_to_complete) FROM learner_metrics)
                THEN 'Fast Completer'
            ELSE 'Average Learner'
        END as persona
    FROM normalized_scores
)
SELECT
    persona,
    COUNT(*) as learner_count,
    ROUND(AVG(completion_rate) * 100, 1) as avg_completion_rate_pct,
    ROUND(AVG(avg_days_to_complete), 1) as avg_completion_days,
    ROUND(AVG(avg_score), 1) as avg_score,
    ROUND(AVG(courses_per_month), 2) as avg_courses_per_month,
    ROUND(AVG(days_since_last_activity), 1) as avg_days_inactive
FROM segment_assignment
GROUP BY persona
ORDER BY learner_count DESC;

-- Individual learner assignments
SELECT
    user_name,
    email,
    persona,
    completed_courses,
    ROUND(completion_rate * 100, 1) as completion_rate_pct,
    ROUND(avg_days_to_complete, 1) as avg_completion_days,
    ROUND(avg_score, 1) as avg_score,
    days_since_last_activity
FROM segment_assignment
ORDER BY persona, completion_rate DESC;
```

### Use Case 9: Course Difficulty Clustering

```sql
-- Cluster courses by difficulty based on learner outcomes
WITH course_metrics AS (
    SELECT
        tr.training_id,
        tr.training_name,
        tr.training_hours,
        COUNT(*) as total_attempts,
        SUM(CASE WHEN t.status = 'Complete' THEN 1 ELSE 0 END) as completions,
        CAST(SUM(CASE WHEN t.status = 'Complete' THEN 1 ELSE 0 END) AS FLOAT) / 
            NULLIF(COUNT(*), 0) as completion_rate,
        AVG(CASE 
            WHEN t.status = 'Complete' 
            THEN DATEDIFF(day, t.assigned_dt, t.completed_dt) 
        END) as avg_completion_days,
        STDEV(CASE 
            WHEN t.status = 'Complete' 
            THEN DATEDIFF(day, t.assigned_dt, t.completed_dt) 
        END) as std_completion_days,
        AVG(CASE WHEN t.status = 'Complete' THEN t.score END) as avg_score,
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY CASE WHEN t.status = 'Complete' THEN t.score END
        ) as median_score,
        SUM(CASE WHEN t.status = 'Withdrawn' THEN 1 ELSE 0 END) as withdrawals,
        CAST(SUM(CASE WHEN t.status = 'Withdrawn' THEN 1 ELSE 0 END) AS FLOAT) / 
            NULLIF(COUNT(*), 0) as dropout_rate,
        AVG(t.attempt_number) as avg_attempts
    FROM training_core tr
    JOIN transcript_core t ON tr.training_id = t.training_id
    WHERE t.assigned_dt >= DATEADD(year, -1, GETDATE())
    GROUP BY tr.training_id, tr.training_name, tr.training_hours
    HAVING COUNT(*) >= 20  -- Minimum sample size
),
difficulty_scoring AS (
    SELECT
        *,
        -- Composite difficulty score (0-100, higher = more difficult)
        CAST(
            (30 * (1 - completion_rate)) +                    -- Non-completion weight
            (20 * (dropout_rate)) +                           -- Dropout weight
            (20 * (1 - (avg_score / 100.0))) +               -- Low score weight
            (15 * LEAST(avg_completion_days / 60.0, 1)) +    -- Time weight
            (15 * LEAST((avg_attempts - 1) / 2.0, 1))        -- Multiple attempts weight
        AS INT) as difficulty_score
    FROM course_metrics
),
difficulty_tiers AS (
    SELECT
        *,
        NTILE(4) OVER (ORDER BY difficulty_score) as difficulty_quartile,
        CASE
            WHEN difficulty_score >= 75 THEN 'Advanced'
            WHEN difficulty_score >= 50 THEN 'Challenging'
            WHEN difficulty_score >= 25 THEN 'Moderate'
            ELSE 'Beginner-Friendly'
        END as difficulty_tier
    FROM difficulty_scoring
)
SELECT
    training_name,
    training_hours,
    total_attempts,
    ROUND(completion_rate * 100, 1) as completion_rate_pct,
    ROUND(avg_completion_days, 1) as avg_days,
    ROUND(avg_score, 1) as avg_score,
    ROUND(dropout_rate * 100, 1) as dropout_rate_pct,
    difficulty_score,
    difficulty_tier,
    difficulty_quartile
FROM difficulty_tiers
ORDER BY difficulty_score DESC;

-- Summary by difficulty tier
SELECT
    difficulty_tier,
    COUNT(*) as course_count,
    ROUND(AVG(completion_rate) * 100, 1) as avg_completion_rate,
    ROUND(AVG(avg_score), 1) as avg_score,
    ROUND(AVG(dropout_rate) * 100, 1) as avg_dropout_rate,
    ROUND(AVG(avg_completion_days), 1) as avg_completion_days
FROM difficulty_tiers
GROUP BY difficulty_tier
ORDER BY 
    CASE difficulty_tier
        WHEN 'Beginner-Friendly' THEN 1
        WHEN 'Moderate' THEN 2
        WHEN 'Challenging' THEN 3
        WHEN 'Advanced' THEN 4
    END;
```

---

## 🔮 FORECASTING QUERIES

### Use Case 5: Training Completion Volume Forecasting

```sql
-- Historical weekly completions for forecasting
WITH weekly_completions AS (
    SELECT
        DATEPART(year, completed_dt) as year,
        DATEPART(week, completed_dt) as week_num,
        DATEADD(week, DATEDIFF(week, 0, completed_dt), 0) as week_start,
        COUNT(*) as completion_count
    FROM transcript_core
    WHERE status = 'Complete'
        AND completed_dt >= DATEADD(year, -2, GETDATE())
        AND completed_dt <= GETDATE()
    GROUP BY 
        DATEPART(year, completed_dt),
        DATEPART(week, completed_dt),
        DATEADD(week, DATEDIFF(week, 0, completed_dt), 0)
),
time_series_features AS (
    SELECT
        week_start,
        completion_count,
        AVG(completion_count) OVER (
            ORDER BY week_start 
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ) as moving_avg_4w,
        STDEV(completion_count) OVER (
            ORDER BY week_start 
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) as rolling_std_12w,
        LAG(completion_count, 52) OVER (ORDER BY week_start) as same_week_last_year,
        ROW_NUMBER() OVER (ORDER BY week_start) as time_index
    FROM weekly_completions
)
SELECT
    week_start,
    completion_count,
    ROUND(moving_avg_4w, 1) as four_week_trend,
    ROUND(rolling_std_12w, 1) as recent_volatility,
    same_week_last_year,
    CASE 
        WHEN same_week_last_year IS NOT NULL 
        THEN ROUND(100.0 * (completion_count - same_week_last_year) / same_week_last_year, 2)
        ELSE NULL 
    END as yoy_change_pct,
    time_index
FROM time_series_features
WHERE week_start >= DATEADD(month, -6, GETDATE())
ORDER BY week_start;

-- Summary statistics for forecast planning
SELECT
    'Last 12 Weeks' as period,
    AVG(completion_count) as avg_completions,
    MIN(completion_count) as min_completions,
    MAX(completion_count) as max_completions,
    STDEV(completion_count) as std_dev,
    PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY completion_count) as p10,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY completion_count) as median,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY completion_count) as p90
FROM weekly_completions
WHERE week_start >= DATEADD(week, -12, GETDATE());
```

---

## 📊 Common Utility Queries

### Date Range Helper
```sql
-- Generate date series for complete time series
WITH RECURSIVE date_series AS (
    SELECT CAST('2024-01-01' AS DATE) as date
    UNION ALL
    SELECT DATEADD(day, 1, date)
    FROM date_series
    WHERE date < CAST('2024-12-31' AS DATE)
)
SELECT * FROM date_series;
```

### Active Users Definition
```sql
-- Standardized active user definition
CREATE VIEW vw_active_users AS
SELECT DISTINCT
    u.user_id,
    u.user_name,
    u.email,
    u.hire_dt,
    u.last_login_dt,
    MAX(t.last_activity_dt) as last_training_activity
FROM users_core u
LEFT JOIN transcript_core t ON u.user_id = t.user_id
WHERE u.user_status_id = 1  -- Active status
    AND (
        u.last_login_dt >= DATEADD(day, -90, GETDATE())
        OR t.last_activity_dt >= DATEADD(day, -90, GETDATE())
    )
GROUP BY u.user_id, u.user_name, u.email, u.hire_dt, u.last_login_dt;
```

### Training Status Summary
```sql
-- Quick status summary by training
SELECT
    tr.training_name,
    COUNT(*) as total_assignments,
    SUM(CASE WHEN t.status = 'Complete' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN t.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
    SUM(CASE WHEN t.status IS NULL THEN 1 ELSE 0 END) as not_started,
    SUM(CASE WHEN t.status = 'Withdrawn' THEN 1 ELSE 0 END) as withdrawn,
    ROUND(100.0 * SUM(CASE WHEN t.status = 'Complete' THEN 1 ELSE 0 END) / COUNT(*), 1) as completion_pct
FROM training_core tr
JOIN transcript_assignment_core ta ON tr.training_id = ta.training_id
LEFT JOIN transcript_core t ON ta.assignment_id = t.transcript_id
GROUP BY tr.training_name
ORDER BY total_assignments DESC;
```

---

## 🎯 Performance Optimization Tips

### 1. Create Indexes
```sql
-- Recommended indexes for analytics queries
CREATE INDEX idx_transcript_core_dates ON transcript_core(assigned_dt, completed_dt);
CREATE INDEX idx_transcript_core_status ON transcript_core(status) INCLUDE (user_id, training_id);
CREATE INDEX idx_transcript_assignment_dates ON transcript_assignment_core(assigned_dt, due_dt);
CREATE INDEX idx_user_ou_primary ON user_ou_core(user_id, primary_flag) WHERE primary_flag = 1;
```

### 2. Materialized View Example
```sql
-- Pre-aggregated completion metrics
CREATE MATERIALIZED VIEW mv_monthly_completion_metrics AS
SELECT
    DATEPART(year, completed_dt) as year,
    DATEPART(month, completed_dt) as month,
    training_id,
    COUNT(*) as completion_count,
    AVG(DATEDIFF(day, assigned_dt, completed_dt)) as avg_completion_days,
    AVG(score) as avg_score
FROM transcript_core
WHERE status = 'Complete'
GROUP BY 
    DATEPART(year, completed_dt),
    DATEPART(month, completed_dt),
    training_id;
```

### 3. Partitioning Strategy
```sql
-- Partition transcript_core by year/month for better performance
ALTER TABLE transcript_core
PARTITION BY RANGE (completed_dt) (
    PARTITION p2023 VALUES LESS THAN ('2024-01-01'),
    PARTITION p2024 VALUES LESS THAN ('2025-01-01'),
    PARTITION p2025 VALUES LESS THAN ('2026-01-01')
);
```

---

This SQL template library provides production-ready queries for implementing the 20 learning analytics use cases. Customize the WHERE clauses, date ranges, and thresholds based on your specific business requirements.
