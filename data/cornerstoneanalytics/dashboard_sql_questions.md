# Dashboard SQL Questions with Use Case Mappings
## 50 Natural Language Questions for Learning Analytics Dashboards

This document provides practical dashboard questions mapped to analytical use cases, pipeline functions, and visualization recommendations.

---

## 📊 BASIC METRICS & KPIs (Questions 1-10)

### Q1: What is the overall completion rate across all active training assignments?
**Use Case:** Foundation for Use Case 2, 7, 17  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe  
**Visualization:** Single metric card / gauge chart  
**Business Value:** Executive dashboard KPI  

**Pipeline Flow:**
```
FilterPipe.filter(user_status='Active')
→ JoinPipe.join(transcript_assignment, transcript)
→ AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'total_assignments': 'count(*)',
    'completed': 'sum(status == "Complete")'
})
```

---

### Q2: Show me the top 10 most popular courses based on enrollment in the last 90 days.
**Use Case:** Related to Use Case 1  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → RankPipe  
**Visualization:** Horizontal bar chart  
**Business Value:** Identify high-demand content  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(assigned_dt, last_90_days)
→ GroupByPipe.group_by(training_id)
→ AggregatePipe.count(assignment_id)
→ JoinPipe.join(training_core, on=training_id)
→ RankPipe.rank_by(enrollment_count, ascending=False)
→ FilterPipe.top_n(10)
```

---

### Q3: What is the total number of overdue assignments right now?
**Use Case:** Foundation for Use Case 7, 17  
**Pipes:** FilterPipe → AggregatePipe  
**Visualization:** Alert metric card with color coding  
**Business Value:** Immediate action required indicator  

**Pipeline Flow:**
```
FilterPipe.filter(due_dt < current_date AND status != 'Complete')
→ AggregatePipe.count(assignment_id)
→ TransformPipe.add_severity_level(
    critical=overdue > 30 days,
    high=overdue > 14 days,
    medium=overdue > 7 days
)
```

---

### Q4: How many employees started training this month versus last month?
**Use Case:** Use Case 1 (Trend Analysis)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Comparison metric cards with trend arrows  
**Business Value:** Track engagement momentum  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(assigned_dt, [this_month, last_month])
→ GroupByPipe.group_by(month)
→ AggregatePipe.count_distinct(user_id)
→ TrendPipe.compare_periods(period1='last_month', period2='this_month')
```

---

### Q5: What percentage of mandatory training is complete across the organization?
**Use Case:** Use Case 17 (Mandatory Compliance)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe  
**Visualization:** Progress bar / gauge chart  
**Business Value:** Compliance dashboard headline metric  

**Pipeline Flow:**
```
FilterPipe.filter(is_mandatory=True)
→ JoinPipe.join(transcript_assignment, transcript, training_requirement_tag)
→ AggregatePipe.aggregate({
    'total_required': 'count(*)',
    'completed': 'sum(status == "Complete")',
    'compliance_rate': 'completed / total_required'
})
```

---

### Q6: Show me completion statistics by department for this quarter.
**Use Case:** Use Case 1 (Enrollment Trends by Department)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → RankPipe  
**Visualization:** Table with conditional formatting or grouped bar chart  
**Business Value:** Department performance comparison  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(completed_dt, current_quarter)
→ JoinPipe.join(user_ou_core, ou_core)
→ GroupByPipe.group_by(ou_name)
→ AggregatePipe.aggregate({
    'total_assignments': 'count(*)',
    'completions': 'sum(status == "Complete")',
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)'
})
→ RankPipe.rank_by(completion_rate, ascending=False)
```

---

### Q7: What are the top 5 courses with the lowest completion rates that are still active?
**Use Case:** Related to Use Case 9 (Course Difficulty)  
**Pipes:** GroupByPipe → AggregatePipe → FilterPipe → RankPipe  
**Visualization:** Horizontal bar chart with red color scheme  
**Business Value:** Identify courses needing intervention  

**Pipeline Flow:**
```
GroupByPipe.group_by(training_id)
→ AggregatePipe.aggregate({
    'total_assignments': 'count(*)',
    'completions': 'sum(status == "Complete")',
    'completion_rate': 'completions / total_assignments'
})
→ FilterPipe.filter(total_assignments >= 20)  # minimum sample
→ RankPipe.rank_by(completion_rate, ascending=True)
→ FilterPipe.top_n(5)
→ JoinPipe.join(training_core)
```

---

### Q8: How many training hours were completed by employees this month?
**Use Case:** Foundation metric  
**Pipes:** FilterPipe → JoinPipe → AggregatePipe  
**Visualization:** Single metric card with month-over-month comparison  
**Business Value:** Training investment tracking  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(completed_dt, this_month)
→ FilterPipe.filter(status='Complete')
→ JoinPipe.join(training_core, on=training_id)
→ AggregatePipe.sum(training_hours)
```

---

### Q9: What's the average time to completion for each training type?
**Use Case:** Related to Use Case 3 (Completion Patterns)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe  
**Visualization:** Grouped bar chart or table  
**Business Value:** Understand learner behavior by content type  

**Pipeline Flow:**
```
FilterPipe.filter(status='Complete')
→ JoinPipe.join(training_core, training_type_core)
→ TransformPipe.calculate(completion_time_days = completed_dt - assigned_dt)
→ GroupByPipe.group_by(training_type_name)
→ AggregatePipe.aggregate({
    'avg_days': 'mean(completion_time_days)',
    'median_days': 'median(completion_time_days)',
    'completion_count': 'count(*)'
})
```

---

### Q10: Show me the count of assignments by status (Complete, In Progress, Not Started, Overdue).
**Use Case:** Foundation for multiple use cases  
**Pipes:** JoinPipe → TransformPipe → GroupByPipe → AggregatePipe  
**Visualization:** Donut chart or stacked bar chart  
**Business Value:** Training pipeline health check  

**Pipeline Flow:**
```
JoinPipe.join(transcript_assignment, transcript)
→ TransformPipe.derive_status(
    'Overdue' if due_dt < current_date AND status != 'Complete',
    'Complete' if status == 'Complete',
    'In Progress' if status == 'In Progress',
    'Not Started' otherwise
)
→ GroupByPipe.group_by(derived_status)
→ AggregatePipe.count(assignment_id)
```

---

## 📈 TREND ANALYSIS (Questions 11-20)

### Q11: Show me the monthly trend of training completions for the past 12 months.
**Use Case:** Use Case 1, 5 (Enrollment Trends, Forecasting)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Line chart with trend line  
**Business Value:** Identify seasonal patterns and overall trajectory  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(completed_dt, last_12_months)
→ FilterPipe.filter(status='Complete')
→ GroupByPipe.group_by(month)
→ AggregatePipe.count(transcript_id)
→ TrendPipe.calculate_moving_average(window=3)
→ TrendPipe.detect_trends(method='linear_regression')
```

---

### Q12: How have new enrollments trended week-over-week for the last quarter?
**Use Case:** Use Case 1 (Enrollment Trends), Use Case 8 (Enrollment Spikes)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → TrendPipe → AnomalyPipe  
**Visualization:** Line chart with anomaly markers  
**Business Value:** Detect unusual enrollment patterns  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(assigned_dt, last_quarter)
→ GroupByPipe.group_by(week)
→ AggregatePipe.count(assignment_id)
→ TrendPipe.calculate_moving_average(window=4)
→ AnomalyPipe.detect_point_anomalies(method='zscore', threshold=2.5)
```

---

### Q13: What's the trend in average completion time over the past 6 months?
**Use Case:** Use Case 6 (Response Time Trends)  
**Pipes:** FilterPipe → TransformPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Line chart with confidence bands  
**Business Value:** Track learner engagement and content effectiveness  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(completed_dt, last_6_months)
→ FilterPipe.filter(status='Complete')
→ TransformPipe.calculate(completion_time = completed_dt - assigned_dt)
→ GroupByPipe.group_by(month)
→ AggregatePipe.median(completion_time)
→ TrendPipe.detect_trends(method='mann_kendall')
```

---

### Q14: Show me the weekly trend of overdue assignments for the past 3 months.
**Use Case:** Use Case 7 (Compliance Risk Trending)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Area chart with alert threshold line  
**Business Value:** Early warning system for compliance issues  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(snapshot_week, last_3_months)
→ FilterPipe.filter(due_dt < snapshot_date AND status != 'Complete')
→ GroupByPipe.group_by(week)
→ AggregatePipe.count(assignment_id)
→ TrendPipe.detect_trends()
→ TrendPipe.detect_change_points(method='pelt')
```

---

### Q15: How has the completion rate changed month-over-month for the Sales department?
**Use Case:** Use Case 1 (Enrollment Trends by Department)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Line chart with previous period comparison  
**Business Value:** Department-specific performance tracking  

**Pipeline Flow:**
```
FilterPipe.filter(ou_name='Sales')
→ GroupByPipe.group_by(month)
→ AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'completions': 'sum(status == "Complete")'
})
→ TrendPipe.calculate_mom_change()
```

---

### Q16: What are the enrollment trends by course category over time?
**Use Case:** Use Case 1 (Enrollment Trends)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → PivotPipe  
**Visualization:** Multi-line chart with category breakdown  
**Business Value:** Content portfolio analysis  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(assigned_dt, last_12_months)
→ JoinPipe.join(training_core, training_type_core)
→ GroupByPipe.group_by([month, training_type_name])
→ AggregatePipe.count(assignment_id)
→ PivotPipe.pivot(index=month, columns=training_type_name)
```

---

### Q17: Show me how our training completion volume compares this year versus last year by month.
**Use Case:** Use Case 5 (Forecasting), Use Case 11 (Period Comparison)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Dual-line chart with year-over-year comparison  
**Business Value:** Year-over-year growth analysis  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(completed_dt, [this_year, last_year])
→ FilterPipe.filter(status='Complete')
→ GroupByPipe.group_by([year, month])
→ AggregatePipe.count(transcript_id)
→ TrendPipe.compare_periods(baseline='last_year', comparison='this_year')
```

---

### Q18: What's the trend in first-attempt pass rates for certification courses?
**Use Case:** Use Case 16 (Instructor Effectiveness), Use Case 11 (Content Impact)  
**Pipes:** FilterPipe → TransformPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Line chart with target threshold  
**Business Value:** Content quality monitoring  

**Pipeline Flow:**
```
FilterPipe.filter(is_certification=True)
→ FilterPipe.filter(attempt_number=1)
→ TransformPipe.calculate(passed = score >= 70)
→ GroupByPipe.group_by(month)
→ AggregatePipe.mean(passed)
→ TrendPipe.detect_trends()
```

---

### Q19: How is employee engagement (active learners) trending over time?
**Use Case:** Use Case 10 (Learner Capacity Planning)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Line chart with moving average  
**Business Value:** Engagement health monitoring  

**Pipeline Flow:**
```
GroupByPipe.group_by(month)
→ AggregatePipe.count_distinct(
    user_id WHERE last_activity_dt >= month_start
)
→ TrendPipe.calculate_moving_average(window=3)
→ TrendPipe.detect_trends(method='linear_regression')
```

---

### Q20: Show me the quarterly trend in training budget consumption vs. forecast.
**Use Case:** Use Case 15 (Training Budget Forecasting)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → ForecastPipe  
**Visualization:** Line chart with actual vs. forecast bands  
**Business Value:** Budget management and forecasting accuracy  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(completed_dt, last_8_quarters)
→ JoinPipe.join(training_core, training_cost)
→ GroupByPipe.group_by(quarter)
→ AggregatePipe.sum(completion_count * cost_per_completion)
→ ForecastPipe.forecast(method='sarima', horizon=4)
→ ForecastPipe.calculate_prediction_intervals()
```

---

## ⚠️ RISK & COMPLIANCE (Questions 21-30)

### Q21: Which learners are at high risk of not completing their assigned training before the deadline?
**Use Case:** Use Case 2 (Non-Completion Risk)  
**Pipes:** FilterPipe → JoinPipe → TransformPipe → RiskPipe → SegmentPipe  
**Visualization:** Table with risk score badges, sortable columns  
**Business Value:** Proactive intervention list  

**Pipeline Flow:**
```
FilterPipe.filter(status IN ['Not Started', 'In Progress'])
→ JoinPipe.join(users_core, transcript_assignment, transcript_core)
→ TransformPipe.add_features([
    'days_since_assignment',
    'days_until_due',
    'historical_completion_rate',
    'days_since_last_login'
])
→ RiskPipe.calculate_risk_scores(
    weights={
      'historical_completion_rate': -0.40,
      'days_until_due': -0.30,
      'days_since_last_login': 0.30
    }
)
→ SegmentPipe.segment_by_risk(thresholds=[0.3, 0.7])
→ FilterPipe.filter(risk_score >= 0.7)  # High risk only
→ RankPipe.rank_by(risk_score, ascending=False)
```

---

### Q22: What departments have the highest compliance risk scores?
**Use Case:** Use Case 7 (Department Compliance Risk)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → RiskPipe → RankPipe  
**Visualization:** Horizontal bar chart with color-coded risk levels  
**Business Value:** Target compliance interventions by department  

**Pipeline Flow:**
```
FilterPipe.filter(is_mandatory=True)
→ JoinPipe.join(user_ou_core, ou_core, transcript_assignment, transcript)
→ GroupByPipe.group_by(ou_name)
→ AggregatePipe.aggregate({
    'overdue_count': 'sum(overdue)',
    'completion_rate': 'mean(status == "Complete")',
    'critical_overdue': 'sum(days_overdue > 30)'
})
→ RiskPipe.calculate_risk_scores(
    weights={
      'completion_rate': -0.50,
      'overdue_rate': 0.30,
      'critical_overdue_rate': 0.20
    }
)
→ RankPipe.rank_by(risk_score, ascending=False)
```

---

### Q23: Show me employees whose certifications are expiring in the next 90 days.
**Use Case:** Use Case 12 (Certification Expiration Risk)  
**Pipes:** FilterPipe → JoinPipe → TransformPipe → RiskPipe → RankPipe  
**Visualization:** Table with urgency indicators and days remaining  
**Business Value:** Prevent certification lapses  

**Pipeline Flow:**
```
FilterPipe.filter(is_certification=True AND status='Complete')
→ TransformPipe.calculate(days_until_expiry = expiration_dt - current_date)
→ FilterPipe.filter(days_until_expiry BETWEEN 0 AND 90)
→ JoinPipe.join(users_core)
→ RiskPipe.calculate_risk_scores(
    features=['days_until_expiry', 'days_since_last_login', 'renewal_history']
)
→ RankPipe.rank_by(days_until_expiry, ascending=True)
```

---

### Q24: Which courses have unusually high dropout rates that need investigation?
**Use Case:** Use Case 3 (Anomaly Detection), Use Case 9 (Course Difficulty)  
**Pipes:** GroupByPipe → AggregatePipe → AnomalyPipe → FilterPipe  
**Visualization:** Table with anomaly flags and historical baselines  
**Business Value:** Content quality issues identification  

**Pipeline Flow:**
```
GroupByPipe.group_by(training_id)
→ AggregatePipe.aggregate({
    'total_assignments': 'count(*)',
    'withdrawals': 'sum(status == "Withdrawn")',
    'dropout_rate': 'withdrawals / total_assignments'
})
→ AnomalyPipe.detect_outliers(
    column='dropout_rate',
    method='iqr',
    threshold=1.5
)
→ FilterPipe.filter(is_anomaly=True)
→ JoinPipe.join(training_core)
→ RankPipe.rank_by(dropout_rate, ascending=False)
```

---

### Q25: What percentage of mandatory training assignments are overdue by manager?
**Use Case:** Use Case 17 (Mandatory Compliance Risk)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → RankPipe  
**Visualization:** Table with manager names, overdue counts, and percentage  
**Business Value:** Manager accountability for team compliance  

**Pipeline Flow:**
```
FilterPipe.filter(is_mandatory=True)
→ JoinPipe.join(users_core, manager relationship)
→ FilterPipe.filter(due_dt < current_date AND status != 'Complete')
→ GroupByPipe.group_by(manager_name)
→ AggregatePipe.aggregate({
    'total_team_assignments': 'count(*)',
    'overdue_assignments': 'sum(is_overdue)',
    'overdue_pct': 'overdue_assignments / total_team_assignments'
})
→ RankPipe.rank_by(overdue_pct, ascending=False)
→ FilterPipe.top_n(10)
```

---

### Q26: Show me learners who haven't started any assigned training in over 30 days.
**Use Case:** Use Case 2 (Risk Scoring), Use Case 4 (Personas - At Risk)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → FilterPipe  
**Visualization:** Alert table with contact information  
**Business Value:** Re-engagement campaign targets  

**Pipeline Flow:**
```
FilterPipe.filter(status IS NULL OR status = 'Not Started')
→ JoinPipe.join(users_core)
→ TransformPipe.calculate(days_since_assignment = current_date - assigned_dt)
→ FilterPipe.filter(days_since_assignment > 30)
→ GroupByPipe.group_by(user_id)
→ AggregatePipe.aggregate({
    'assignments_not_started': 'count(*)',
    'oldest_assignment_days': 'max(days_since_assignment)'
})
→ RankPipe.rank_by(oldest_assignment_days, ascending=False)
```

---

### Q27: What's our organization-wide compliance rate for each mandatory training requirement?
**Use Case:** Use Case 17 (Mandatory Compliance)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe  
**Visualization:** Progress bar chart or table with color coding  
**Business Value:** Audit readiness dashboard  

**Pipeline Flow:**
```
FilterPipe.filter(is_mandatory=True)
→ JoinPipe.join(training_requirement_tag, transcript_assignment, transcript)
→ GroupByPipe.group_by(requirement_name)
→ AggregatePipe.aggregate({
    'total_required': 'count(*)',
    'completed': 'sum(status == "Complete")',
    'compliance_rate': 'completed / total_required',
    'overdue': 'sum(is_overdue)'
})
→ RankPipe.rank_by(compliance_rate, ascending=True)  # Show worst first
```

---

### Q28: Which training programs have the highest rate of learners requiring multiple attempts?
**Use Case:** Use Case 9 (Course Difficulty)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → RankPipe  
**Visualization:** Horizontal bar chart with attempt distribution  
**Business Value:** Identify courses needing instructional redesign  

**Pipeline Flow:**
```
FilterPipe.filter(status='Complete')
→ GroupByPipe.group_by(training_id)
→ AggregatePipe.aggregate({
    'total_completions': 'count(*)',
    'multiple_attempts': 'sum(attempt_number > 1)',
    'multiple_attempt_rate': 'multiple_attempts / total_completions',
    'avg_attempts': 'mean(attempt_number)'
})
→ FilterPipe.filter(total_completions >= 20)
→ RankPipe.rank_by(multiple_attempt_rate, ascending=False)
→ FilterPipe.top_n(10)
```

---

### Q29: Show me teams with declining completion rates over the past 3 months.
**Use Case:** Use Case 1 (Trends), Use Case 7 (Dept Risk)  
**Pipes:** FilterPipe → JoinPipe → GroupByPipe → AggregatePipe → TrendPipe  
**Visualization:** Table with trend indicators (arrows) and sparklines  
**Business Value:** Early warning for team performance issues  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(completed_dt, last_3_months)
→ JoinPipe.join(user_ou_core, ou_core)
→ GroupByPipe.group_by([ou_name, month])
→ AggregatePipe.mean(status == 'Complete')
→ TrendPipe.detect_trends(group_by='ou_name')
→ FilterPipe.filter(trend_direction='Declining' AND trend_significance=True)
→ RankPipe.rank_by(trend_strength, ascending=True)  # Most negative first
```

---

### Q30: What's the distribution of risk scores across all active training assignments?
**Use Case:** Use Case 2 (Risk Scoring)  
**Pipes:** FilterPipe → RiskPipe → SegmentPipe → GroupByPipe → AggregatePipe  
**Visualization:** Histogram or distribution chart  
**Business Value:** Overall portfolio risk assessment  

**Pipeline Flow:**
```
FilterPipe.filter(status IN ['Not Started', 'In Progress'])
→ RiskPipe.calculate_risk_scores()
→ SegmentPipe.segment_by_risk(
    bins=[0, 0.3, 0.5, 0.7, 1.0],
    labels=['Low', 'Medium', 'High', 'Critical']
)
→ GroupByPipe.group_by(risk_category)
→ AggregatePipe.count(assignment_id)
```

---

## 🔍 ANOMALY DETECTION & INSIGHTS (Questions 31-40)

### Q31: Are there any courses with suspiciously fast completion times?
**Use Case:** Use Case 3 (Unusual Completion Patterns)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → AnomalyPipe  
**Visualization:** Scatter plot with anomaly highlights  
**Business Value:** Detect potential cheating or data quality issues  

**Pipeline Flow:**
```
FilterPipe.filter(status='Complete')
→ TransformPipe.calculate(completion_time = completed_dt - assigned_dt)
→ GroupByPipe.group_by(training_id)
→ AggregatePipe.aggregate({
    'median_completion_time': 'median(completion_time)',
    'min_completion_time': 'min(completion_time)',
    'estimated_duration': 'first(training_hours * 24)'  # hours to days
})
→ AnomalyPipe.detect_outliers(
    column='min_completion_time',
    method='isolation_forest'
)
→ FilterPipe.filter(min_completion_time < estimated_duration * 0.1)
→ JoinPipe.join(training_core)
```

---

### Q32: Show me any unusual spikes in course enrollments in the last 30 days.
**Use Case:** Use Case 8 (Enrollment Spikes)  
**Pipes:** FilterPipe → GroupByPipe → AggregatePipe → AnomalyPipe  
**Visualization:** Time series with anomaly markers  
**Business Value:** Detect bulk assignments or system issues  

**Pipeline Flow:**
```
FilterPipe.filter_by_date(assigned_dt, last_30_days)
→ GroupByPipe.group_by([date, training_id])
→ AggregatePipe.count(assignment_id)
→ AnomalyPipe.detect_point_anomalies(
    method='mad',  # Median Absolute Deviation
    threshold=3.5
)
→ FilterPipe.filter(is_anomaly=True)
→ JoinPipe.join(training_core)
→ RankPipe.rank_by([anomaly_severity, date], ascending=[False, False])
```

---

### Q33: Which learners have completion patterns that deviate from their peers?
**Use Case:** Use Case 3 (Anomaly Detection), Use Case 4 (Segmentation)  
**Pipes:** GroupByPipe → AggregatePipe → AnomalyPipe → FilterPipe  
**Visualization:** Table with anomaly scores and patterns  
**Business Value:** Identify outlier learners for personalized support  

**Pipeline Flow:**
```
GroupByPipe.group_by(user_id)
→ AggregatePipe.aggregate({
    'avg_completion_days': 'mean(completion_time_days)',
    'completion_rate': 'mean(status == "Complete")',
    'courses_per_month': 'count(*) / months_active'
})
→ AnomalyPipe.detect_outliers(
    columns=['avg_completion_days', 'completion_rate', 'courses_per_month'],
    method='isolation_forest'
)
→ FilterPipe.filter(is_anomaly=True)
→ JoinPipe.join(users_core)
```

---

### Q34: Are there courses with unusually high or low average scores?
**Use Case:** Use Case 18 (Unusual Scoring Patterns)  
**Pipes:** GroupByPipe → AggregatePipe → AnomalyPipe → FilterPipe  
**Visualization:** Box plot with outlier highlights  
**Business Value:** Content difficulty calibration  

**Pipeline Flow:**
```
FilterPipe.filter(status='Complete' AND score IS NOT NULL)
→ GroupByPipe.group_by(training_id)
→ AggregatePipe.aggregate({
    'avg_score': 'mean(score)',
    'median_score': 'median(score)',
    'std_score': 'std(score)',
    'sample_size': 'count(*)'
})
→ FilterPipe.filter(sample_size >= 20)
→ AnomalyPipe.detect_outliers(
    column='avg_score',
    method='iqr',
    threshold=1.5
)
→ JoinPipe.join(training_core)
```

---

### Q35: Show me learners who are taking courses in unexpected sequences.
**Use Case:** Use Case 13 (Learning Path Deviation)  
**Pipes:** GroupByPipe → SequencePipe → AnomalyPipe → FilterPipe  
**Visualization:** Sankey diagram showing actual vs. expected paths  
**Business Value:** Improve learning path design and guidance  

**Pipeline Flow:**
```
GroupByPipe.group_by(user_id)
→ SortPipe.sort_by(completed_dt)
→ AggregatePipe.collect_list(training_id)
→ SequencePipe.calculate_sequence_similarity(
    actual='completed_courses',
    expected='recommended_path'
)
→ AnomalyPipe.detect_sequence_anomalies(threshold=0.3)
→ FilterPipe.filter(deviation_score > 0.6)
→ JoinPipe.join(users_core)
```

---

### Q36: What training programs have score distributions that don't look normal?
**Use Case:** Use Case 18 (Unusual Scoring Patterns)  
**Pipes:** GroupByPipe → StatsPipe → AnomalyPipe  
**Visualization:** Multiple histograms or violin plots  
**Business Value:** Assessment quality control  

**Pipeline Flow:**
```
FilterPipe.filter(status='Complete' AND score IS NOT NULL)
→ GroupByPipe.group_by(training_id)
→ StatsPipe.test_distribution_normality(method='shapiro')
→ AnomalyPipe.detect_distribution_anomalies(
    expected_distribution='normal',
    significance=0.05
)
→ FilterPipe.filter(is_distribution_anomaly=True)
→ JoinPipe.join(training_core)
```

---

### Q37: Are there geographic regions with unusual performance patterns?
**Use Case:** Use Case 14 (Geographic Performance)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → AnomalyPipe  
**Visualization:** Heat map or choropleth map  
**Business Value:** Identify regional training challenges  

**Pipeline Flow:**
```
JoinPipe.join(users_core, address_core, transcript_core)
→ GroupByPipe.group_by([country_code, subdivision1])
→ AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)',
    'learner_count': 'count_distinct(user_id)'
})
→ FilterPipe.filter(learner_count >= 20)
→ AnomalyPipe.detect_outliers(
    columns=['completion_rate', 'avg_score'],
    method='dbscan'
)
```

---

### Q38: Show me instructors whose classes have performance outliers.
**Use Case:** Use Case 16 (Instructor Effectiveness)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → AnomalyPipe  
**Visualization:** Table with instructor comparisons  
**Business Value:** Instructor quality assurance  

**Pipeline Flow:**
```
JoinPipe.join(transcript_core, session_core, instructor)
→ GroupByPipe.group_by(instructor_name)
→ AggregatePipe.aggregate({
    'avg_completion_rate': 'mean(status == "Complete")',
    'avg_learner_score': 'mean(score)',
    'avg_satisfaction': 'mean(rating)',
    'session_count': 'count_distinct(session_id)'
})
→ FilterPipe.filter(session_count >= 5)
→ AnomalyPipe.detect_outliers(
    columns=['avg_completion_rate', 'avg_learner_score'],
    method='iqr'
)
```

---

### Q39: Which departments have enrollment patterns that differ significantly from the organization average?
**Use Case:** Use Case 8 (Anomaly Detection), Use Case 1 (Trends)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → AnomalyPipe  
**Visualization:** Deviation bar chart  
**Business Value:** Identify departments needing targeted campaigns  

**Pipeline Flow:**
```
JoinPipe.join(user_ou_core, ou_core, transcript_assignment)
→ GroupByPipe.group_by([ou_name, month])
→ AggregatePipe.count(assignment_id)
→ TransformPipe.calculate_deviation_from_mean(group_by='month')
→ AnomalyPipe.detect_contextual_anomalies(
    context_columns=['month'],
    threshold=2.0
)
```

---

### Q40: Show me courses where completion time variance is unusually high.
**Use Case:** Use Case 3 (Completion Patterns), Use Case 9 (Difficulty)  
**Pipes:** GroupByPipe → AggregatePipe → AnomalyPipe → RankPipe  
**Visualization:** Error bar chart showing variance  
**Business Value:** Identify courses with inconsistent learner experiences  

**Pipeline Flow:**
```
FilterPipe.filter(status='Complete')
→ TransformPipe.calculate(completion_time = completed_dt - assigned_dt)
→ GroupByPipe.group_by(training_id)
→ AggregatePipe.aggregate({
    'mean_days': 'mean(completion_time)',
    'std_days': 'std(completion_time)',
    'coefficient_of_variation': 'std_days / mean_days',
    'sample_size': 'count(*)'
})
→ FilterPipe.filter(sample_size >= 30)
→ AnomalyPipe.detect_outliers(
    column='coefficient_of_variation',
    method='zscore'
)
→ RankPipe.rank_by(coefficient_of_variation, ascending=False)
```

---

## 👥 SEGMENTATION & COMPARISON (Questions 41-50)

### Q41: How do our learner personas compare in terms of completion rates and engagement?
**Use Case:** Use Case 4 (Learner Personas)  
**Pipes:** GroupByPipe → AggregatePipe → SegmentPipe → ComparisonPipe  
**Visualization:** Grouped bar chart or radar chart  
**Business Value:** Personalization strategy development  

**Pipeline Flow:**
```
GroupByPipe.group_by(user_id)
→ AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'avg_days_to_complete': 'mean(completion_time_days)',
    'courses_per_month': 'count(*) / months_active'
})
→ SegmentPipe.perform_clustering(
    method='kmeans',
    n_clusters=5,
    features=['completion_rate', 'avg_days_to_complete', 'courses_per_month']
)
→ SegmentPipe.profile_segments()
→ SegmentPipe.compare_segments(test_type='anova')
```

---

### Q42: Show me completion rates by delivery method (classroom, online, blended).
**Use Case:** Use Case 19 (Learning Style Profiling)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → ComparisonPipe  
**Visualization:** Grouped bar chart with statistical significance markers  
**Business Value:** Optimize delivery method investments  

**Pipeline Flow:**
```
JoinPipe.join(transcript_core, training_core, delivery_method)
→ GroupByPipe.group_by(delivery_method_name)
→ AggregatePipe.aggregate({
    'total_assignments': 'count(*)',
    'completions': 'sum(status == "Complete")',
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)',
    'avg_satisfaction': 'mean(rating)'
})
→ StatsPipe.test_differences(test='chi_square')
```

---

### Q43: Compare training performance across different job roles.
**Use Case:** Use Case 4 (Segmentation), Use Case 14 (Geographic - but by role)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → RankPipe  
**Visualization:** Table with sparklines for trends  
**Business Value:** Role-specific training needs analysis  

**Pipeline Flow:**
```
JoinPipe.join(users_core, transcript_core)
→ GroupByPipe.group_by(job_title)
→ AggregatePipe.aggregate({
    'employee_count': 'count_distinct(user_id)',
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)',
    'courses_per_employee': 'count(*) / employee_count'
})
→ FilterPipe.filter(employee_count >= 10)
→ RankPipe.rank_by(completion_rate, ascending=False)
```

---

### Q44: How do the difficulty levels of our courses distribute across categories?
**Use Case:** Use Case 9 (Course Difficulty Clustering)  
**Pipes:** GroupByPipe → AggregatePipe → SegmentPipe → PivotPipe  
**Visualization:** Stacked bar chart or heat map  
**Business Value:** Portfolio balance assessment  

**Pipeline Flow:**
```
GroupByPipe.group_by(training_id)
→ AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'avg_completion_days': 'mean(completion_time_days)',
    'dropout_rate': 'mean(status == "Withdrawn")'
})
→ SegmentPipe.perform_clustering(
    method='hierarchical',
    n_clusters=4
)
→ SegmentPipe.label_segments(
    labels=['Beginner', 'Moderate', 'Challenging', 'Advanced']
)
→ JoinPipe.join(training_core, training_type_core)
→ PivotPipe.pivot(
    index='training_type',
    columns='difficulty_tier',
    values='count'
)
```

---

### Q45: Show me how completion rates vary by employee tenure.
**Use Case:** Use Case 4 (Segmentation)  
**Pipes:** JoinPipe → TransformPipe → SegmentPipe → GroupByPipe → AggregatePipe  
**Visualization:** Line chart or bar chart with tenure groups  
**Business Value:** Onboarding and retention insights  

**Pipeline Flow:**
```
JoinPipe.join(users_core, transcript_core)
→ TransformPipe.calculate(
    tenure_months = months_between(current_date, hire_dt)
)
→ SegmentPipe.create_bins(
    column='tenure_months',
    bins=[0, 3, 6, 12, 24, 60, 999],
    labels=['0-3mo', '3-6mo', '6-12mo', '1-2yr', '2-5yr', '5yr+']
)
→ GroupByPipe.group_by(tenure_group)
→ AggregatePipe.aggregate({
    'employee_count': 'count_distinct(user_id)',
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)'
})
```

---

### Q46: What are the key differences between high-performing and low-performing departments?
**Use Case:** Use Case 1 (Trends), Use Case 7 (Dept Risk)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → SegmentPipe → ComparisonPipe  
**Visualization:** Side-by-side comparison cards  
**Business Value:** Best practice identification  

**Pipeline Flow:**
```
JoinPipe.join(user_ou_core, ou_core, transcript_core)
→ GroupByPipe.group_by(ou_name)
→ AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)',
    'courses_per_employee': 'count(*) / count_distinct(user_id)',
    'avg_time_to_complete': 'mean(completion_time_days)'
})
→ SegmentPipe.segment_by_percentile(
    column='completion_rate',
    percentiles=[0.25, 0.75],
    labels=['Low Performing', 'Medium', 'High Performing']
)
→ SegmentPipe.compare_segments(
    segment1='High Performing',
    segment2='Low Performing'
)
```

---

### Q47: How does training effectiveness compare across different training vendors or platforms?
**Use Case:** Use Case 11 (Content Impact)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → RankPipe  
**Visualization:** Comparison table with ratings  
**Business Value:** Vendor performance evaluation  

**Pipeline Flow:**
```
JoinPipe.join(training_core, vendor_info, transcript_core)
→ GroupByPipe.group_by(vendor_name)
→ AggregatePipe.aggregate({
    'course_count': 'count_distinct(training_id)',
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)',
    'avg_satisfaction': 'mean(rating)',
    'total_enrollments': 'count(*)'
})
→ FilterPipe.filter(total_enrollments >= 50)
→ RankPipe.rank_by(avg_satisfaction, ascending=False)
```

---

### Q48: Compare the learning behaviors of remote vs. office-based employees.
**Use Case:** Use Case 4 (Segmentation), Use Case 19 (Learning Styles)  
**Pipes:** JoinPipe → SegmentPipe → GroupByPipe → AggregatePipe → ComparisonPipe  
**Visualization:** Dual-column comparison with key metrics  
**Business Value:** Optimize training delivery for work models  

**Pipeline Flow:**
```
JoinPipe.join(users_core, employee_location, transcript_core)
→ SegmentPipe.create_segments(
    column='work_location_type',
    segments=['Remote', 'Office', 'Hybrid']
)
→ GroupByPipe.group_by(work_location_type)
→ AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'preferred_delivery': 'mode(delivery_method)',
    'avg_study_time': 'mean(time_on_platform)',
    'weekend_learning_pct': 'mean(completed_on_weekend)'
})
→ SegmentPipe.compare_segments()
```

---

### Q49: Show me how course preferences differ by generation (Gen Z, Millennial, Gen X, Boomer).
**Use Case:** Use Case 4 (Segmentation), Use Case 19 (Learning Styles)  
**Pipes:** JoinPipe → TransformPipe → SegmentPipe → GroupByPipe → AggregatePipe  
**Visualization:** Stacked bar chart or heat map  
**Business Value:** Demographic-based content strategy  

**Pipeline Flow:**
```
JoinPipe.join(users_core, transcript_core, training_core)
→ TransformPipe.calculate_age(birth_dt)
→ SegmentPipe.create_bins(
    column='age',
    bins=[18, 27, 43, 59, 100],
    labels=['Gen Z', 'Millennial', 'Gen X', 'Boomer']
)
→ GroupByPipe.group_by([generation, training_type])
→ AggregatePipe.count(transcript_id)
→ PivotPipe.pivot(
    index='generation',
    columns='training_type',
    values='count'
)
→ TransformPipe.normalize_by_row()  # Convert to percentages
```

---

### Q50: What are the completion patterns for employees in different time zones?
**Use Case:** Use Case 19 (Learning Style Profiling)  
**Pipes:** JoinPipe → GroupByPipe → AggregatePipe → SegmentPipe  
**Visualization:** World map with completion metrics or grouped bar chart  
**Business Value:** Global training schedule optimization  

**Pipeline Flow:**
```
JoinPipe.join(users_core, timezone_core, transcript_core)
→ TransformPipe.extract_hour(last_activity_dt)
→ GroupByPipe.group_by(timezone_name)
→ AggregatePipe.aggregate({
    'learner_count': 'count_distinct(user_id)',
    'completion_rate': 'mean(status == "Complete")',
    'peak_activity_hour': 'mode(activity_hour)',
    'weekend_learning_pct': 'mean(is_weekend)',
    'avg_session_duration': 'mean(session_minutes)'
})
→ SegmentPipe.profile_segments()
```

---

## 📋 Quick Reference: Question Categories

### Basic Metrics & KPIs (Q1-Q10)
- Current state snapshots
- Simple aggregations
- Top/bottom rankings
- Status distributions

### Trend Analysis (Q11-Q20)
- Time series patterns
- Period comparisons
- Moving averages
- Change detection

### Risk & Compliance (Q21-Q30)
- Risk scoring
- Compliance monitoring
- Early warnings
- Manager accountability

### Anomaly Detection (Q31-Q40)
- Outlier identification
- Pattern deviations
- Quality control
- Investigation triggers

### Segmentation & Comparison (Q41-Q50)
- Group profiling
- Comparative analysis
- Demographic patterns
- Performance benchmarking

---

## 🎨 Visualization Type Summary

| Visualization | Best For | Sample Questions |
|--------------|----------|------------------|
| **Single Metric Card** | KPIs, alerts | Q1, Q3, Q5 |
| **Bar Chart** | Comparisons, rankings | Q2, Q6, Q22 |
| **Line Chart** | Trends over time | Q11, Q13, Q19 |
| **Donut/Pie Chart** | Status distributions | Q10 |
| **Table** | Detailed lists, risk scores | Q21, Q25, Q38 |
| **Heat Map** | Geographic or matrix data | Q37, Q44 |
| **Scatter Plot** | Anomaly detection | Q31, Q40 |
| **Progress Bar** | Compliance tracking | Q5, Q27 |
| **Stacked Bar** | Comparative composition | Q11, Q49 |
| **Box Plot** | Distribution analysis | Q34 |

---

## 💡 Implementation Priority Guide

### Phase 1: Foundation (Weeks 1-2)
Start with basic metrics and trends:
- Q1, Q2, Q3, Q5, Q6, Q10 (Basic KPIs)
- Q11, Q13 (Basic trends)

### Phase 2: Risk & Compliance (Weeks 3-4)
Add proactive monitoring:
- Q21, Q22, Q23, Q27 (Risk identification)
- Q14, Q29 (Risk trends)

### Phase 3: Insights & Anomalies (Weeks 5-6)
Enable deeper analysis:
- Q31, Q32, Q34 (Anomaly detection)
- Q41, Q42, Q43 (Segmentation basics)

### Phase 4: Advanced Analytics (Weeks 7-8)
Complete the picture:
- Q35, Q36, Q38 (Advanced anomalies)
- Q46, Q47, Q48, Q50 (Advanced segmentation)

---

## 🔗 Mapping to Main Use Cases

| Question Range | Primary Use Cases |
|----------------|-------------------|
| Q1-Q10 | Foundation for all use cases |
| Q11-Q20 | Use Cases 1, 5, 6, 10, 11, 15, 16 |
| Q21-Q30 | Use Cases 2, 7, 9, 12, 17 |
| Q31-Q40 | Use Cases 3, 8, 13, 18 |
| Q41-Q50 | Use Cases 4, 9, 14, 19, 20 |

---

This comprehensive question bank provides production-ready dashboard queries that can be directly implemented using the pipeline functions and SQL templates from the previous documents. Each question includes clear mapping to use cases, required pipes, visualization recommendations, and business value.
