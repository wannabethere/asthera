# Learning Analytics Use Cases - Table Requirements
## Database Table Mappings for Each Use Case

This document specifies the exact tables, fields, and join relationships needed to implement each of the 20 analytical use cases.

---

## Use Case 1: Course Enrollment Trends by Department

### Primary Tables
1. **transcript_assignment_core**
   - assignment_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - due_dt
   - assigned_by_user_id

2. **user_ou_core**
   - user_ou_id (PK)
   - user_id (FK)
   - ou_id (FK)
   - ou_type_id (FK)
   - primary_flag

3. **ou_core**
   - ou_id (PK)
   - ou_name
   - ou_code
   - parent_ou_id

4. **training_core**
   - training_id (PK)
   - training_name
   - training_code
   - training_type_id

### Supporting Tables
- **ou_type_core**: ou_type_id, ou_type_name (for filtering department vs other org types)
- **training_type_core**: training_type_id, training_type (optional for filtering)

### Key Joins
```
transcript_assignment_core.user_id = user_ou_core.user_id
user_ou_core.ou_id = ou_core.ou_id
transcript_assignment_core.training_id = training_core.training_id
user_ou_core.ou_type_id = ou_type_core.ou_type_id
```

### Date/Time Fields
- assigned_dt (for time series grouping by month/quarter)

---

## Use Case 2: Predicting Course Non-Completion Risk

### Primary Tables
1. **transcript_assignment_core**
   - assignment_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - due_dt
   - status (In Progress, Complete, etc.)

2. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - completed_dt
   - status
   - score
   - attempt_number

3. **users_core**
   - user_id (PK)
   - user_status_id
   - hire_dt
   - termination_dt
   - last_login_dt

4. **training_core**
   - training_id (PK)
   - training_name
   - estimated_duration
   - training_type_id

### Supporting Tables
- **user_status_core**: user_status_id, status_name (Active, Terminated, etc.)
- **transcript_status_local_core**: For status definitions

### Key Joins
```
transcript_assignment_core.assignment_id = transcript_core.transcript_id
transcript_assignment_core.user_id = users_core.user_id
transcript_assignment_core.training_id = training_core.training_id
users_core.user_status_id = user_status_core.user_status_id
```

### Derived Features Needed
- days_since_assignment (CURRENT_DATE - assigned_dt)
- days_until_due (due_dt - CURRENT_DATE)
- previous_completion_rate (aggregate from transcript_core by user)
- overdue_assignments_count (count where due_dt < CURRENT_DATE AND status != 'Complete')

---

## Use Case 3: Unusual Completion Patterns (Anomaly Detection)

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - completed_dt
   - status
   - score

2. **training_core**
   - training_id (PK)
   - training_name
   - estimated_duration
   - training_hours

### Supporting Tables
- **users_core**: user_id, user_name (for investigation)
- **transcript_delivery_method_local_core**: delivery_method (to control for delivery type)

### Key Joins
```
transcript_core.training_id = training_core.training_id
transcript_core.user_id = users_core.user_id
```

### Derived Features Needed
- completion_time_days (completed_dt - assigned_dt)
- completion_time_vs_estimated (completion_time_days / training_hours)

---

## Use Case 4: Learner Persona Development (Segmentation)

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - completed_dt
   - status
   - score
   - last_activity_dt

2. **users_core**
   - user_id (PK)
   - user_name
   - email
   - user_status_id
   - hire_dt

3. **training_core**
   - training_id (PK)
   - training_type_id
   - estimated_duration

### Supporting Tables
- **training_type_core**: training_type_id, training_type_name
- **user_login_core**: user_id, login_dt (for activity patterns)

### Key Joins
```
transcript_core.user_id = users_core.user_id
transcript_core.training_id = training_core.training_id
training_core.training_type_id = training_type_core.training_type_id
users_core.user_id = user_login_core.user_id
```

### Aggregations Needed (by user_id)
- completion_rate: AVG(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END)
- avg_days_to_complete: AVG(completed_dt - assigned_dt) WHERE status = 'Complete'
- courses_completed: COUNT(*) WHERE status = 'Complete'
- courses_in_progress: COUNT(*) WHERE status = 'In Progress'
- avg_score: AVG(score) WHERE status = 'Complete'
- days_since_last_activity: CURRENT_DATE - MAX(last_activity_dt)

---

## Use Case 5: Training Completion Volume Forecasting

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - completed_dt
   - status

### Supporting Tables
- **training_core**: training_id, training_name (for breakdown by course type)
- **training_type_core**: training_type_id, training_type_name

### Key Joins
```
transcript_core.training_id = training_core.training_id
training_core.training_type_id = training_type_core.training_type_id
```

### Time Series Aggregation
- Group by: week or month (DATE_TRUNC('week', completed_dt))
- Metric: COUNT(transcript_id) WHERE status = 'Complete'

---

## Use Case 6: Training Assignment Response Time Trends

### Primary Tables
1. **transcript_assignment_core**
   - assignment_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt

2. **transcript_core**
   - transcript_id (PK)
   - assignment_id (FK)
   - first_activity_dt
   - last_activity_dt

3. **user_ou_core**
   - user_id (FK)
   - ou_id (FK)

4. **ou_core**
   - ou_id (PK)
   - ou_name

### Key Joins
```
transcript_assignment_core.assignment_id = transcript_core.transcript_id
transcript_assignment_core.user_id = user_ou_core.user_id
user_ou_core.ou_id = ou_core.ou_id
```

### Derived Metrics
- response_time_days: first_activity_dt - assigned_dt
- Group by: assigned_month, ou_id

---

## Use Case 7: Department Compliance Risk Scoring

### Primary Tables
1. **user_ou_core**
   - user_ou_id (PK)
   - user_id (FK)
   - ou_id (FK)
   - primary_flag

2. **ou_core**
   - ou_id (PK)
   - ou_name
   - ou_code
   - parent_ou_id

3. **transcript_assignment_core**
   - assignment_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - due_dt

4. **transcript_core**
   - transcript_id (PK)
   - assignment_id (FK)
   - status
   - completed_dt

### Supporting Tables
- **training_requirement_tag_core**: For identifying mandatory training
  - requirement_tag_id (PK)
  - training_id (FK)
  - is_mandatory

### Key Joins
```
user_ou_core.user_id = transcript_assignment_core.user_id
user_ou_core.ou_id = ou_core.ou_id
transcript_assignment_core.assignment_id = transcript_core.transcript_id
transcript_assignment_core.training_id = training_requirement_tag_core.training_id
```

### Aggregations by ou_id
- overdue_count: COUNT(*) WHERE due_dt < CURRENT_DATE AND status != 'Complete'
- total_assignments: COUNT(*)
- completion_rate: AVG(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END)
- avg_days_overdue: AVG(CURRENT_DATE - due_dt) WHERE status != 'Complete'
- critical_overdue: COUNT(*) WHERE CURRENT_DATE - due_dt > 30

---

## Use Case 8: Sudden Enrollment Spikes (Anomaly Detection)

### Primary Tables
1. **transcript_assignment_core**
   - assignment_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - assigned_by_user_id

2. **training_core**
   - training_id (PK)
   - training_name
   - training_code

### Supporting Tables
- **users_core**: assigned_by_user_id (for understanding who made bulk assignments)

### Key Joins
```
transcript_assignment_core.training_id = training_core.training_id
transcript_assignment_core.assigned_by_user_id = users_core.user_id
```

### Time Series Aggregation
- Group by: assigned_date (DATE(assigned_dt)), training_id
- Metric: COUNT(assignment_id)

---

## Use Case 9: Course Difficulty Clustering (Segmentation)

### Primary Tables
1. **training_core**
   - training_id (PK)
   - training_name
   - estimated_duration
   - training_hours
   - training_type_id

2. **transcript_core**
   - transcript_id (PK)
   - training_id (FK)
   - status
   - score
   - attempt_number
   - assigned_dt
   - completed_dt

### Supporting Tables
- **training_type_core**: training_type_id, training_type_name
- **training_delivery_method_local_core**: delivery_method information

### Key Joins
```
transcript_core.training_id = training_core.training_id
training_core.training_type_id = training_type_core.training_type_id
```

### Aggregations by training_id
- completion_rate: AVG(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END)
- avg_completion_days: AVG(completed_dt - assigned_dt) WHERE status = 'Complete'
- median_score: MEDIAN(score) WHERE status = 'Complete'
- dropout_rate: AVG(CASE WHEN status = 'Withdrawn' THEN 1 ELSE 0 END)
- avg_attempts: AVG(attempt_number)
- time_variance: STDDEV(completed_dt - assigned_dt)

---

## Use Case 10: Learner Capacity Planning (Forecasting)

### Primary Tables
1. **users_core**
   - user_id (PK)
   - user_status_id
   - hire_dt
   - termination_dt

2. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - last_activity_dt
   - status

### Supporting Tables
- **user_status_core**: user_status_id, status_name
- **user_login_core**: user_id, login_dt (for activity determination)

### Key Joins
```
users_core.user_id = transcript_core.user_id
users_core.user_status_id = user_status_core.user_status_id
users_core.user_id = user_login_core.user_id
```

### Active Learner Definition
Users with last_activity_dt >= month_start OR login_dt >= month_start

### Time Series Aggregation
- Group by: month
- Metric: COUNT(DISTINCT user_id) WHERE active

---

## Use Case 11: Course Material Update Impact (Trend Analysis)

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - completed_dt
   - status
   - score

2. **training_core**
   - training_id (PK)
   - training_name
   - modified_dt (or custom field for major updates)
   - version_number

3. **UserRating** (if available)
   - user_id (FK)
   - training_id (FK)
   - rating
   - rating_dt

### Key Joins
```
transcript_core.training_id = training_core.training_id
transcript_core.user_id = UserRating.user_id
transcript_core.training_id = UserRating.training_id
```

### Period Definition
- before: completed_dt < training_core.modified_dt
- after: completed_dt >= training_core.modified_dt

### Metrics to Compare
- completion_rate
- avg_score
- avg_rating
- avg_completion_time

---

## Use Case 12: Certification Expiration Risk Scoring

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - completed_dt
   - expiration_dt
   - status

2. **training_core**
   - training_id (PK)
   - is_certification (boolean or flag)
   - certification_valid_months

3. **users_core**
   - user_id (PK)
   - last_login_dt
   - email
   - user_status_id

4. **user_login_core**
   - user_id (FK)
   - login_dt

### Key Joins
```
transcript_core.training_id = training_core.training_id
transcript_core.user_id = users_core.user_id
users_core.user_id = user_login_core.user_id
```

### Derived Features
- days_until_expiry: expiration_dt - CURRENT_DATE
- days_since_last_login: CURRENT_DATE - MAX(login_dt)
- previous_renewal_count: COUNT(*) WHERE user_id and is_certification GROUP BY user
- renewal_rate: historical renewals / expirations

---

## Use Case 13: Learning Path Deviation (Anomaly Detection)

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - completed_dt
   - status

2. **training_core**
   - training_id (PK)
   - training_name
   - training_category (or curriculum_id)
   - prerequisite_training_id
   - sequence_number

3. **users_core**
   - user_id (PK)
   - user_name
   - email

### Supporting Tables
- **curriculum_core** (if available): Defines recommended learning paths
- **training_prerequisite** (if available): prerequisite relationships

### Key Joins
```
transcript_core.user_id = users_core.user_id
transcript_core.training_id = training_core.training_id
training_core.prerequisite_training_id = training_core.training_id (self-join)
```

### Analysis Approach
- Collect sequence of training_id per user_id (ordered by completed_dt)
- Compare to recommended path from curriculum
- Calculate similarity metrics

---

## Use Case 14: Geographic Performance Clustering (Segmentation)

### Primary Tables
1. **users_core**
   - user_id (PK)
   - address_id (FK)
   - user_name

2. **address_core**
   - address_id (PK)
   - country_code
   - subdivision1 (state/province)
   - city
   - postal_code

3. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - status
   - score
   - assigned_dt
   - completed_dt
   - last_activity_dt

### Key Joins
```
users_core.address_id = address_core.address_id
users_core.user_id = transcript_core.user_id
```

### Aggregations by Geography (country_code, subdivision1)
- learner_count: COUNT(DISTINCT user_id)
- completion_rate: AVG(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END)
- avg_score: AVG(score) WHERE status = 'Complete'
- engagement_rate: AVG(active_days / total_days)
- dropout_rate: AVG(CASE WHEN status = 'Withdrawn' THEN 1 ELSE 0 END)
- avg_time_to_complete: AVG(completed_dt - assigned_dt)

---

## Use Case 15: Training Budget Forecasting

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - completed_dt
   - status

2. **training_core**
   - training_id (PK)
   - training_name
   - training_type_id
   - cost_per_completion (custom field or joined table)

3. **training_type_core**
   - training_type_id (PK)
   - training_type_name

### Supporting Tables
- **training_cost** (custom table if available): training_id, cost_per_seat, exam_fee, materials_cost

### Key Joins
```
transcript_core.training_id = training_core.training_id
training_core.training_type_id = training_type_core.training_type_id
training_core.training_id = training_cost.training_id
```

### Time Series Aggregation
- Group by: fiscal_quarter, training_type
- Metric: COUNT(*) WHERE status = 'Complete'
- Budget = completions * cost_per_completion

---

## Use Case 16: Instructor Effectiveness Trends

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - session_id (FK)
   - status
   - score
   - completed_dt

2. **session_core** (if available)
   - session_id (PK)
   - training_id (FK)
   - session_start_dt
   - session_end_dt
   - instructor_user_id

3. **users_core** (for instructors)
   - user_id (PK)
   - user_name

4. **UserRating**
   - user_id (FK - learner)
   - training_id (FK)
   - session_id (FK)
   - rating
   - rating_dt

### Key Joins
```
transcript_core.session_id = session_core.session_id
session_core.instructor_user_id = users_core.user_id
transcript_core.user_id = UserRating.user_id
transcript_core.session_id = UserRating.session_id
```

### Aggregations by instructor_id, quarter
- avg_completion_rate
- avg_learner_score
- avg_satisfaction: AVG(rating)
- session_count: COUNT(DISTINCT session_id)
- learner_count: COUNT(DISTINCT user_id)

---

## Use Case 17: Mandatory Training Compliance Risk

### Primary Tables
1. **training_requirement_tag_core**
   - requirement_tag_id (PK)
   - training_id (FK)
   - is_mandatory
   - requirement_name

2. **transcript_assignment_core**
   - assignment_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt
   - due_dt

3. **transcript_core**
   - transcript_id (PK)
   - assignment_id (FK)
   - status
   - completed_dt

4. **user_ou_core**
   - user_ou_id (PK)
   - user_id (FK)
   - ou_id (FK)

5. **ou_core**
   - ou_id (PK)
   - ou_name

### Key Joins
```
training_requirement_tag_core.training_id = transcript_assignment_core.training_id
transcript_assignment_core.assignment_id = transcript_core.transcript_id
transcript_assignment_core.user_id = user_ou_core.user_id
user_ou_core.ou_id = ou_core.ou_id
```

### Filters
- is_mandatory = TRUE

### Aggregations by ou_id, requirement_id
- total_required: COUNT(DISTINCT user_id)
- completed: SUM(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END)
- in_progress: SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END)
- not_started: total_required - (completed + in_progress)
- overdue: COUNT(*) WHERE due_dt < CURRENT_DATE AND status != 'Complete'
- critical_overdue: COUNT(*) WHERE CURRENT_DATE - due_dt > 30

---

## Use Case 18: Unusual Scoring Patterns (Anomaly Detection)

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - session_id (FK)
   - status
   - score
   - completed_dt

2. **training_core**
   - training_id (PK)
   - training_name
   - training_type_id

3. **session_core** (if analyzing by session)
   - session_id (PK)
   - training_id (FK)
   - session_start_dt

### Key Joins
```
transcript_core.training_id = training_core.training_id
transcript_core.session_id = session_core.session_id
```

### Aggregations by training_id, session_id
- score_mean: AVG(score)
- score_median: MEDIAN(score)
- score_std: STDDEV(score)
- score_min: MIN(score)
- score_max: MAX(score)
- learner_count: COUNT(*)
- perfect_score_pct: AVG(CASE WHEN score = 100 THEN 1 ELSE 0 END)
- failing_score_pct: AVG(CASE WHEN score < 70 THEN 1 ELSE 0 END)

### Filters
- status = 'Complete'
- score IS NOT NULL
- learner_count >= 10 (minimum sample size)

---

## Use Case 19: Learning Style Profiling (Segmentation)

### Primary Tables
1. **transcript_core**
   - transcript_id (PK)
   - user_id (FK)
   - training_id (FK)
   - status
   - completed_dt
   - assigned_dt
   - last_activity_dt

2. **training_core**
   - training_id (PK)
   - delivery_method (or delivery_method_id FK)
   - training_type_id
   - training_hours

3. **training_delivery_method_local_core**
   - delivery_method_id (PK)
   - delivery_method_name (Video, Instructor-Led, E-Learning, etc.)

4. **training_type_core**
   - training_type_id (PK)
   - training_type_name (Technical, Soft Skills, Leadership, etc.)

5. **users_core**
   - user_id (PK)
   - user_name
   - timezone_id

### Key Joins
```
transcript_core.training_id = training_core.training_id
training_core.delivery_method_id = training_delivery_method_local_core.delivery_method_id
training_core.training_type_id = training_type_core.training_type_id
transcript_core.user_id = users_core.user_id
```

### Aggregations by user_id
- prefers_video: AVG(CASE WHEN delivery_method = 'Video' THEN 1 ELSE 0 END)
- prefers_classroom: AVG(CASE WHEN delivery_method = 'Instructor-Led' THEN 1 ELSE 0 END)
- prefers_elearning: AVG(CASE WHEN delivery_method = 'E-Learning' THEN 1 ELSE 0 END)
- avg_course_hours: AVG(training_hours)
- prefers_short_courses: AVG(CASE WHEN training_hours < 2 THEN 1 ELSE 0 END)
- prefers_long_courses: AVG(CASE WHEN training_hours > 8 THEN 1 ELSE 0 END)
- completion_speed: AVG((completed_dt - assigned_dt) / training_hours)
- prefers_technical: AVG(CASE WHEN training_type = 'Technical' THEN 1 ELSE 0 END)
- prefers_soft_skills: AVG(CASE WHEN training_type = 'Soft Skills' THEN 1 ELSE 0 END)
- weekend_learner: AVG(CASE WHEN DAYOFWEEK(completed_dt) IN (1,7) THEN 1 ELSE 0 END)
- evening_learner: AVG(CASE WHEN HOUR(last_activity_dt) >= 17 THEN 1 ELSE 0 END)

---

## Use Case 20: Skill Gap Closure Timeline (Forecasting)

### Primary Tables
1. **UserSkillMap**
   - user_id (FK)
   - skill_id (FK)
   - current_skill_level
   - required_skill_level

2. **UserSkills**
   - skill_id (PK)
   - skill_name
   - skill_category

3. **skill_training_map** (custom mapping table)
   - skill_id (FK)
   - training_id (FK)
   - proficiency_gain (how much this training improves the skill)

4. **transcript_assignment_core**
   - assignment_id (PK)
   - user_id (FK)
   - training_id (FK)
   - assigned_dt

5. **transcript_core**
   - transcript_id (PK)
   - assignment_id (FK)
   - status
   - completed_dt
   - assigned_dt

6. **training_core**
   - training_id (PK)
   - training_name
   - training_hours

### Key Joins
```
UserSkillMap.user_id = transcript_assignment_core.user_id
UserSkillMap.skill_id = skill_training_map.skill_id
skill_training_map.training_id = transcript_assignment_core.training_id
transcript_assignment_core.assignment_id = transcript_core.transcript_id
skill_training_map.training_id = training_core.training_id
```

### Filters
- current_skill_level < required_skill_level (identifies gaps)

### Aggregations by skill_id, training_id
- users_needing_training: COUNT(DISTINCT user_id)
- users_enrolled: COUNT(DISTINCT CASE WHEN assignment_id IS NOT NULL THEN user_id END)
- users_completed: COUNT(DISTINCT CASE WHEN status = 'Complete' THEN user_id END)
- gap_size: users_needing_training - users_completed
- avg_completion_time: AVG(completed_dt - assigned_dt) WHERE status = 'Complete'
- weekly_completion_rate: COUNT(*) / weeks_in_period WHERE status = 'Complete'

---

## Summary: Most Frequently Used Tables

### Core Tables (Used in 15+ Use Cases)
1. **transcript_core** (20/20 use cases)
2. **training_core** (19/20 use cases)
3. **users_core** (18/20 use cases)
4. **transcript_assignment_core** (15/20 use cases)

### Frequently Used Tables (Used in 5-14 Use Cases)
5. **user_ou_core** (8/20 use cases)
6. **ou_core** (8/20 use cases)
7. **training_type_core** (7/20 use cases)
8. **user_status_core** (5/20 use cases)
9. **training_requirement_tag_core** (5/20 use cases)

### Specialized Tables (Used in Specific Use Cases)
- **address_core**: Geographic analysis (Use Case 14)
- **UserRating**: Satisfaction analysis (Use Cases 11, 16)
- **UserSkillMap / UserSkills**: Skill gap analysis (Use Case 20)
- **user_login_core**: Activity patterns (Use Cases 4, 10, 12)
- **session_core**: Instructor analysis (Use Cases 16, 18)
- **training_delivery_method_local_core**: Learning style analysis (Use Case 19)

---

## Join Relationship Summary

### Primary Relationships
```
users_core.user_id → transcript_core.user_id
users_core.user_id → transcript_assignment_core.user_id
users_core.user_id → user_ou_core.user_id
users_core.address_id → address_core.address_id

training_core.training_id → transcript_core.training_id
training_core.training_id → transcript_assignment_core.training_id

transcript_assignment_core.assignment_id → transcript_core.transcript_id

user_ou_core.ou_id → ou_core.ou_id
training_core.training_type_id → training_type_core.training_type_id
```

### Common Filtering Patterns
1. **Active Learners**: users_core.user_status_id = 'Active'
2. **Completed Training**: transcript_core.status = 'Complete'
3. **Overdue Assignments**: transcript_assignment_core.due_dt < CURRENT_DATE AND status != 'Complete'
4. **Mandatory Training**: training_requirement_tag_core.is_mandatory = TRUE
5. **Primary Department**: user_ou_core.primary_flag = TRUE

---

## Implementation Notes

### Data Quality Considerations
1. **Null Handling**: Many date fields (completed_dt, expiration_dt) may be NULL for in-progress training
2. **Active Records**: Use _last_touched_dt_utc to identify recently updated records
3. **Historical Data**: Consider archival patterns - some tables may only have recent data
4. **Sample Size**: Filter out groups with insufficient sample size (n < 20-30) for statistical analysis

### Performance Tips
1. **Indexing**: Ensure indexes on user_id, training_id, assigned_dt, completed_dt
2. **Partitioning**: Consider date-based partitioning for transcript_core and transcript_assignment_core
3. **Materialized Views**: Pre-aggregate commonly used metrics (completion rates, etc.)
4. **Incremental Processing**: Use _last_touched_dt_utc for incremental data loads

### Custom Fields/Tables Needed
Some use cases reference fields/tables that may need to be created:
1. **training_core.modified_dt**: Track content update dates (Use Case 11)
2. **training_core.is_certification**: Flag certification courses (Use Case 12)
3. **training_cost**: Table for cost per completion (Use Case 15)
4. **skill_training_map**: Mapping between skills and training (Use Case 20)
5. **session_core.instructor_user_id**: Link instructors to sessions (Use Case 16)
6. **curriculum_core**: Recommended learning paths (Use Case 13)

---

## Quick Reference: Use Case → Primary Tables

| Use Case # | Primary Tables (Top 3) |
|-----------|------------------------|
| 1 | transcript_assignment_core, user_ou_core, ou_core |
| 2 | transcript_assignment_core, transcript_core, users_core |
| 3 | transcript_core, training_core |
| 4 | transcript_core, users_core, training_core |
| 5 | transcript_core, training_core |
| 6 | transcript_assignment_core, transcript_core, user_ou_core |
| 7 | user_ou_core, transcript_assignment_core, transcript_core |
| 8 | transcript_assignment_core, training_core |
| 9 | training_core, transcript_core |
| 10 | users_core, transcript_core, user_login_core |
| 11 | transcript_core, training_core, UserRating |
| 12 | transcript_core, training_core, users_core |
| 13 | transcript_core, training_core, users_core |
| 14 | users_core, address_core, transcript_core |
| 15 | transcript_core, training_core, training_type_core |
| 16 | transcript_core, session_core, users_core |
| 17 | training_requirement_tag_core, transcript_assignment_core, user_ou_core |
| 18 | transcript_core, training_core, session_core |
| 19 | transcript_core, training_core, training_delivery_method_local_core |
| 20 | UserSkillMap, transcript_assignment_core, transcript_core |

This mapping provides a complete reference for implementing each analytical use case with the correct database tables and fields.
