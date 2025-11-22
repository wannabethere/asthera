# Learning Analytics Use Cases
## 20 Advanced Analytical Examples Using Pipes and Data Models

---

## 1. TREND ANALYSIS: Course Enrollment Trends by Department

**Natural Language Question:**
"Show me how course enrollments have trended over the past 12 months across different departments, and identify which departments show declining engagement."

**Reasoning Plan:**
1. Join users_core with user_ou_core to get department assignments
2. Join with transcript_assignment_core to get enrollment data
3. Filter by assigned_dt within last 12 months
4. Use TrendPipe.detect_trends() to identify upward/downward trends
5. Use TrendPipe.decompose_trend() to separate seasonal patterns from true trends
6. Use TrendPipe.calculate_trend_strength() to quantify trend magnitude

**Answer:**
```
Pipeline Flow:
- FilterPipe.filter_by_date(assigned_dt, last_12_months)
- JoinPipe.join(users_core, user_ou_core, on=user_id)
- JoinPipe.join(transcript_assignment_core, on=user_id)
- GroupByPipe.group_by([ou_name, month])
- AggregatePipe.count(assignment_id)
- TrendPipe.detect_trends(method='mann_kendall', confidence=0.95)
- TrendPipe.decompose_trend(model='additive')
- TrendPipe.calculate_trend_strength()
```

**Insights Generated:**
- Monthly enrollment trends by department
- Departments with statistically significant declining trends
- Seasonal patterns vs actual trend direction
- Trend strength coefficients for prioritization

---

## 2. RISK SCORING: Predicting Course Non-Completion Risk

**Natural Language Question:**
"Identify learners who are at high risk of not completing their assigned training and calculate a risk score for each."

**Reasoning Plan:**
1. Gather historical completion data from transcript_core
2. Identify features: days_since_assignment, previous_completion_rate, overdue_count, user_status
3. Use RiskPipe.calculate_risk_scores() with logistic regression
4. Use RiskPipe.identify_risk_factors() to find key predictors
5. Use SegmentPipe.segment_by_risk() to create risk tiers (low/medium/high)
6. Generate actionable recommendations

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_assignment_core, transcript_core, on=assignment_id)
- JoinPipe.join(users_core, on=user_id)
- FilterPipe.filter(status='In Progress')
- TransformPipe.add_features([
    'days_since_assignment',
    'days_until_due',
    'previous_completion_rate',
    'overdue_assignments_count'
  ])
- RiskPipe.train_risk_model(
    target='completion_status',
    method='logistic_regression',
    features=['days_since_assignment', 'days_until_due', 'previous_completion_rate']
  )
- RiskPipe.calculate_risk_scores()
- RiskPipe.identify_risk_factors(top_n=5)
- SegmentPipe.segment_by_risk(thresholds=[0.3, 0.7])
```

**Insights Generated:**
- Risk score (0-1) for each active learner
- Top 5 risk factors with feature importance
- Segmentation: High Risk (>0.7), Medium Risk (0.3-0.7), Low Risk (<0.3)
- Recommended interventions based on risk factors

---

## 3. ANOMALY DETECTION: Unusual Completion Patterns

**Natural Language Question:**
"Find courses or users with unusual completion patterns that deviate significantly from normal behavior."

**Reasoning Plan:**
1. Calculate typical completion time distribution from transcript_core
2. Use AnomalyPipe.detect_outliers() with IQR and Z-score methods
3. Use AnomalyPipe.detect_anomalous_patterns() for time-series anomalies
4. Flag anomalies for investigation (possible data quality issues or gaming)
5. Use AnomalyPipe.explain_anomalies() to understand why flagged

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_core, training_core, on=training_id)
- FilterPipe.filter(status='Complete')
- TransformPipe.calculate_completion_time(
    completed_dt - assigned_dt
  )
- AnomalyPipe.detect_outliers(
    column='completion_time_days',
    method='iqr',
    threshold=3.0
  )
- AnomalyPipe.detect_outliers(
    column='completion_time_days',
    method='isolation_forest',
    contamination=0.05
  )
- AnomalyPipe.detect_anomalous_patterns(
    time_column='completed_dt',
    value_column='completion_time_days',
    window_size=30
  )
- AnomalyPipe.explain_anomalies(top_features=5)
```

**Insights Generated:**
- List of anomalous completions with anomaly scores
- Courses with suspiciously fast completion times
- Users with abnormal completion patterns
- Potential data quality issues or policy violations
- Root cause analysis for each anomaly type

---

## 4. SEGMENTATION: Learner Persona Development

**Natural Language Question:**
"Segment learners into distinct personas based on their learning behavior, engagement patterns, and completion rates."

**Reasoning Plan:**
1. Aggregate learner metrics: completion_rate, avg_days_to_complete, courses_per_quarter
2. Use SegmentPipe.perform_clustering() with k-means
3. Use SegmentPipe.profile_segments() to characterize each persona
4. Use SegmentPipe.find_optimal_segments() to determine best number of clusters
5. Use SegmentPipe.compare_segments() to understand differences

**Answer:**
```
Pipeline Flow:
- GroupByPipe.group_by(user_id)
- AggregatePipe.aggregate({
    'completion_rate': 'mean(status=="Complete")',
    'avg_days_to_complete': 'mean(completion_time_days)',
    'courses_completed': 'count(status=="Complete")',
    'courses_in_progress': 'count(status=="In Progress")',
    'avg_score': 'mean(score)',
    'days_since_last_activity': 'max(last_activity_dt)'
  })
- SegmentPipe.find_optimal_segments(method='elbow', max_k=10)
- SegmentPipe.perform_clustering(
    method='kmeans',
    n_clusters=5,
    features=['completion_rate', 'avg_days_to_complete', 'courses_completed']
  )
- SegmentPipe.profile_segments(
    metrics=['mean', 'median', 'count']
  )
- SegmentPipe.compare_segments(test_type='anova')
```

**Insights Generated:**
- 5 learner personas (e.g., "High Achievers", "Strugglers", "Inactive", "Steady Performers", "Fast Completers")
- Profile for each persona with key characteristics
- Statistical differences between segments
- Recommendations for targeted interventions per persona

---

## 5. FORECAST: Predicting Training Completion Volume

**Natural Language Question:**
"Forecast how many course completions we'll have in the next 3 months to plan certification processing capacity."

**Reasoning Plan:**
1. Aggregate historical completion counts by week from transcript_core
2. Use ForecastPipe.prepare_time_series() to structure data
3. Use ForecastPipe.forecast() with SARIMA for seasonal patterns
4. Use ForecastPipe.calculate_prediction_intervals() for confidence bands
5. Use ForecastPipe.validate_forecast() with backtesting

**Answer:**
```
Pipeline Flow:
- FilterPipe.filter(status='Complete')
- GroupByPipe.group_by([week])
- AggregatePipe.count(transcript_id)
- ForecastPipe.prepare_time_series(
    date_column='week',
    value_column='completion_count'
  )
- ForecastPipe.detect_seasonality(
    periods=[52]  # weekly seasonality
  )
- ForecastPipe.forecast(
    method='sarima',
    horizon=12,  # 12 weeks (3 months)
    seasonal_periods=52
  )
- ForecastPipe.calculate_prediction_intervals(
    confidence_levels=[0.80, 0.95]
  )
- ForecastPipe.validate_forecast(
    method='rolling_window',
    validation_size=12
  )
```

**Insights Generated:**
- Week-by-week completion forecasts for next 12 weeks
- 80% and 95% prediction intervals
- Expected total completions: [forecast range]
- Model accuracy metrics (MAPE, RMSE)
- Seasonal patterns identified
- Capacity planning recommendations

---

## 6. TREND ANALYSIS: Training Assignment Response Time

**Natural Language Question:**
"Analyze the trend in how quickly learners start their assigned training after receiving it, and identify if response times are improving or declining."

**Reasoning Plan:**
1. Calculate days between assignment and first activity
2. Use TrendPipe.detect_trends() for statistical trend detection
3. Use TrendPipe.calculate_moving_average() to smooth noise
4. Use TrendPipe.detect_change_points() to find when behavior changed
5. Segment by user_ou to identify department-specific trends

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_assignment_core, transcript_core, on=assignment_id)
- TransformPipe.calculate_response_time(
    first_activity_dt - assigned_dt
  )
- FilterPipe.filter(response_time_days >= 0)
- GroupByPipe.group_by([assigned_month])
- AggregatePipe.median(response_time_days)
- TrendPipe.calculate_moving_average(window=3)
- TrendPipe.detect_trends(method='linear_regression')
- TrendPipe.detect_change_points(method='pelt', min_distance=3)
- TrendPipe.compare_periods(
    baseline_period='Q1_2024',
    comparison_period='Q4_2024'
  )
```

**Insights Generated:**
- Median response time trend over time
- Statistically significant trend direction (improving/declining)
- Change points where behavior significantly shifted
- Period-over-period comparison
- Departments with best/worst trends

---

## 7. RISK SCORING: Department Compliance Risk

**Natural Language Question:**
"Calculate a compliance risk score for each department based on overdue training assignments and historical completion rates."

**Reasoning Plan:**
1. Aggregate department-level metrics from user_ou_core and transcript_assignment_core
2. Use RiskPipe.calculate_risk_scores() with weighted scoring
3. Use RiskPipe.identify_risk_factors() to find key drivers
4. Use AnomalyPipe.flag_high_risk_entities() for immediate attention
5. Generate risk-adjusted timelines for remediation

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(user_ou_core, transcript_assignment_core, on=user_id)
- JoinPipe.join(transcript_core, on=assignment_id)
- GroupByPipe.group_by(ou_id)
- AggregatePipe.aggregate({
    'overdue_count': 'sum(due_dt < current_date AND status != "Complete")',
    'total_assignments': 'count(assignment_id)',
    'completion_rate': 'mean(status == "Complete")',
    'avg_days_overdue': 'mean(days_overdue WHERE status != "Complete")',
    'critical_overdue': 'sum(days_overdue > 30)'
  })
- RiskPipe.calculate_risk_scores(
    weights={
      'overdue_rate': 0.40,
      'avg_days_overdue': 0.30,
      'critical_overdue': 0.20,
      'completion_rate': -0.10  # negative weight (higher is better)
    }
  )
- RiskPipe.normalize_scores(method='min_max')
- AnomalyPipe.flag_high_risk_entities(threshold=0.75)
- RankPipe.rank_by(risk_score, ascending=False)
```

**Insights Generated:**
- Risk score (0-100) for each department
- Weighted risk factors contribution
- Departments requiring immediate intervention
- Projected remediation timeline based on historical completion velocity
- Recommended action plans per risk level

---

## 8. ANOMALY DETECTION: Sudden Enrollment Spikes

**Natural Language Question:**
"Detect unusual spikes or drops in course enrollment that might indicate system issues, policy changes, or data quality problems."

**Reasoning Plan:**
1. Create time series of daily enrollments from transcript_assignment_core
2. Use AnomalyPipe.detect_point_anomalies() for individual outliers
3. Use AnomalyPipe.detect_contextual_anomalies() for unusual patterns
4. Use AnomalyPipe.detect_collective_anomalies() for sequential anomalies
5. Use TrendPipe.detect_change_points() to validate significant shifts

**Answer:**
```
Pipeline Flow:
- GroupByPipe.group_by([assigned_date, training_id])
- AggregatePipe.count(assignment_id)
- PivotPipe.pivot(
    index='assigned_date',
    columns='training_id',
    values='assignment_count'
  )
- AnomalyPipe.detect_point_anomalies(
    method='mad',  # Median Absolute Deviation
    threshold=3.5
  )
- AnomalyPipe.detect_contextual_anomalies(
    context_columns=['day_of_week', 'month'],
    threshold=2.5
  )
- AnomalyPipe.detect_collective_anomalies(
    window_size=7,
    method='discord'
  )
- TrendPipe.detect_change_points(method='binary_segmentation')
- AnomalyPipe.explain_anomalies(method='shap')
```

**Insights Generated:**
- List of anomalous dates with severity scores
- Type of anomaly (spike, drop, pattern change)
- Courses most affected by anomalies
- Potential root causes (e.g., mass assignments, system issues)
- Recommended investigation priorities

---

## 9. SEGMENTATION: Course Difficulty Clustering

**Natural Language Question:**
"Segment courses into difficulty tiers based on completion rates, average completion time, and learner performance."

**Reasoning Plan:**
1. Aggregate course-level metrics from transcript_core and training_core
2. Use SegmentPipe.perform_clustering() with hierarchical clustering
3. Use SegmentPipe.profile_segments() to understand characteristics
4. Use SegmentPipe.visualize_segments() for dendrograms
5. Use metadata to validate difficulty assumptions

**Answer:**
```
Pipeline Flow:
- GroupByPipe.group_by(training_id)
- AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'avg_completion_days': 'mean(completion_time_days)',
    'median_score': 'median(score)',
    'dropout_rate': 'mean(status == "Withdrawn")',
    'avg_attempts': 'mean(attempt_number)',
    'time_variance': 'std(completion_time_days)'
  })
- SegmentPipe.normalize_features(method='zscore')
- SegmentPipe.find_optimal_segments(
    method='silhouette',
    max_k=8
  )
- SegmentPipe.perform_clustering(
    method='hierarchical',
    n_clusters=4,
    linkage='ward'
  )
- SegmentPipe.profile_segments()
- JoinPipe.join(training_core, on=training_id)
- SegmentPipe.compare_segments(
    categorical_vars=['training_type', 'delivery_method']
  )
```

**Insights Generated:**
- 4 difficulty tiers: "Beginner-Friendly", "Moderate", "Challenging", "Advanced"
- Profile for each tier with key statistics
- Course assignments to difficulty segments
- Validation against metadata (e.g., hours, prerequisites)
- Recommendations for course difficulty labeling

---

## 10. FORECAST: Learner Capacity Planning

**Natural Language Question:**
"Forecast the number of active learners we'll have each month for the next quarter to plan instructor and support resources."

**Reasoning Plan:**
1. Calculate historical active learner counts from users_core and transcript_core
2. Use ForecastPipe.forecast() with multiple methods (ARIMA, ETS, Prophet)
3. Use ForecastPipe.ensemble_forecasts() to combine predictions
4. Use ForecastPipe.scenario_analysis() for best/worst case planning
5. Account for seasonality (e.g., summer drops)

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(users_core, transcript_core, on=user_id)
- FilterPipe.filter(last_activity_dt >= month_start)
- GroupByPipe.group_by(month)
- AggregatePipe.count_distinct(user_id)
- ForecastPipe.prepare_time_series(
    date_column='month',
    value_column='active_learners'
  )
- ForecastPipe.detect_seasonality(periods=[12])
- ForecastPipe.forecast(
    methods=['arima', 'ets', 'prophet'],
    horizon=3
  )
- ForecastPipe.ensemble_forecasts(
    method='weighted_average',
    weights=[0.4, 0.3, 0.3]
  )
- ForecastPipe.scenario_analysis(
    percentiles=[0.10, 0.50, 0.90]  # pessimistic, base, optimistic
  )
- ForecastPipe.calculate_forecast_accuracy()
```

**Insights Generated:**
- Monthly active learner forecasts for next 3 months
- Ensemble predictions with confidence intervals
- Scenario analysis: worst case, base case, best case
- Resource recommendations (instructors, support staff)
- Seasonal adjustment factors

---

## 11. TREND ANALYSIS: Course Material Update Impact

**Natural Language Question:**
"Analyze how course completion rates and learner satisfaction trended before and after major content updates."

**Reasoning Plan:**
1. Identify course update dates from training_core metadata
2. Use TrendPipe.compare_periods() for before/after analysis
3. Use TrendPipe.test_trend_significance() for statistical validation
4. Use TrendPipe.calculate_trend_velocity() to measure rate of change
5. Control for external factors (seasonality, user mix)

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_core, training_core, on=training_id)
- FilterPipe.filter(training_id IN updated_courses)
- TransformPipe.add_period_label(
    before='completed_dt < update_dt',
    after='completed_dt >= update_dt'
  )
- GroupByPipe.group_by([training_id, period, month])
- AggregatePipe.aggregate({
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)',
    'avg_rating': 'mean(rating)',
    'completion_time': 'mean(completion_time_days)'
  })
- TrendPipe.compare_periods(
    period1='before',
    period2='after',
    metrics=['completion_rate', 'avg_score', 'avg_rating']
  )
- TrendPipe.test_trend_significance(method='t_test')
- TrendPipe.calculate_effect_size(method='cohens_d')
- TrendPipe.control_for_seasonality()
```

**Insights Generated:**
- Before/after comparison for each metric
- Statistical significance of changes (p-values)
- Effect size (practical significance)
- Courses with most improved metrics
- Seasonally-adjusted impact estimates
- ROI of content updates

---

## 12. RISK SCORING: Certification Expiration Risk

**Natural Language Question:**
"Score users based on their risk of having certifications expire without renewal, considering their engagement patterns and historical behavior."

**Reasoning Plan:**
1. Join transcript_core with certification expiration dates
2. Calculate features: days_until_expiry, last_login, previous_renewal_behavior
3. Use RiskPipe.calculate_risk_scores() with survival analysis
4. Use RiskPipe.calculate_time_to_event() to estimate when action needed
5. Generate proactive outreach recommendations

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_core, training_core, on=training_id)
- FilterPipe.filter(is_certification=True AND status='Complete')
- TransformPipe.add_features([
    'days_until_expiry',
    'days_since_last_login',
    'previous_renewal_count',
    'renewal_rate',
    'engagement_score'
  ])
- FilterPipe.filter(days_until_expiry > 0)
- RiskPipe.train_risk_model(
    method='survival_analysis',
    time_column='days_until_expiry',
    event_column='renewed',
    features=['days_since_last_login', 'previous_renewal_count', 'engagement_score']
  )
- RiskPipe.calculate_risk_scores()
- RiskPipe.calculate_time_to_event(percentile=0.5)
- SegmentPipe.segment_by_risk(
    thresholds=[0.25, 0.75],
    labels=['Low Risk', 'Medium Risk', 'High Risk']
  )
- RankPipe.rank_by([risk_score, days_until_expiry])
```

**Insights Generated:**
- Expiration risk score (0-1) for each certified user
- Estimated time until likely lapse
- Risk segmentation for targeted outreach
- Key risk factors (e.g., low engagement, no prior renewals)
- Recommended outreach timing and messaging
- Prioritized contact list

---

## 13. ANOMALY DETECTION: Learning Path Deviation

**Natural Language Question:**
"Identify learners who are taking courses in unusual sequences that deviate from recommended learning paths."

**Reasoning Plan:**
1. Define canonical learning paths from curriculum metadata
2. Extract actual course sequences from transcript_core
3. Use AnomalyPipe.detect_sequence_anomalies() for pattern detection
4. Use SequencePipe.calculate_sequence_similarity() for path comparison
5. Flag high-deviation learners for guidance

**Answer:**
```
Pipeline Flow:
- GroupByPipe.group_by(user_id)
- SortPipe.sort_by(completed_dt)
- AggregatePipe.collect_list(training_id)
- JoinPipe.join(recommended_paths, on=training_category)
- SequencePipe.calculate_sequence_similarity(
    actual='completed_courses',
    expected='recommended_path',
    method='levenshtein'
  )
- AnomalyPipe.detect_sequence_anomalies(
    threshold=0.3  # similarity < 0.3 is anomalous
  )
- TransformPipe.calculate_deviation_score()
- FilterPipe.filter(deviation_score > 0.6)
- JoinPipe.join(users_core, on=user_id)
- SegmentPipe.segment_by_deviation(
    bins=[0, 0.3, 0.6, 1.0],
    labels=['On Track', 'Minor Deviation', 'Major Deviation']
  )
```

**Insights Generated:**
- List of learners with significant path deviations
- Deviation scores and similarity metrics
- Common deviation patterns
- Potential reasons (prerequisites skipped, wrong sequence)
- Recommended corrective actions
- Success rate comparison: on-path vs off-path learners

---

## 14. SEGMENTATION: Geographic Performance Clustering

**Natural Language Question:**
"Segment learners by geographic region and identify regions with similar learning outcomes and engagement patterns."

**Reasoning Plan:**
1. Join users_core with address_core for geographic data
2. Aggregate metrics by region: completion_rate, engagement, scores
3. Use SegmentPipe.perform_clustering() to find similar regions
4. Use SegmentPipe.profile_segments() for regional characteristics
5. Use StatsPipe.test_regional_differences() for validation

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(users_core, address_core, on=address_id)
- JoinPipe.join(transcript_core, on=user_id)
- GroupByPipe.group_by([country_code, subdivision1])
- AggregatePipe.aggregate({
    'learner_count': 'count_distinct(user_id)',
    'completion_rate': 'mean(status == "Complete")',
    'avg_score': 'mean(score)',
    'engagement_rate': 'mean(active_days / total_days)',
    'dropout_rate': 'mean(status == "Withdrawn")',
    'avg_time_to_complete': 'mean(completion_time_days)'
  })
- FilterPipe.filter(learner_count >= 20)  # minimum sample size
- SegmentPipe.normalize_features()
- SegmentPipe.perform_clustering(
    method='kmeans',
    n_clusters=6,
    features=['completion_rate', 'avg_score', 'engagement_rate']
  )
- SegmentPipe.profile_segments()
- SegmentPipe.compare_segments(test_type='kruskal_wallis')
```

**Insights Generated:**
- 6 regional clusters with distinct performance profiles
- Cluster profiles (e.g., "High Performers", "Struggling Regions", "Disengaged")
- Geographic distribution of each cluster
- Statistical differences between clusters
- Best practices from top-performing regions
- Targeted intervention strategies per cluster

---

## 15. FORECAST: Training Budget Forecasting

**Natural Language Question:**
"Forecast training completion volume by training type to budget for certification exam fees and materials for the next fiscal year."

**Reasoning Plan:**
1. Aggregate historical completions by training_type and quarter
2. Use ForecastPipe.forecast_by_category() for each training type
3. Use ForecastPipe.forecast_total() for overall budget
4. Join with cost data to calculate budget requirements
5. Use ForecastPipe.scenario_analysis() for budget sensitivity

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_core, training_core, on=training_id)
- FilterPipe.filter(status='Complete')
- GroupByPipe.group_by([fiscal_quarter, training_type])
- AggregatePipe.count(transcript_id)
- PivotPipe.pivot(
    index='fiscal_quarter',
    columns='training_type',
    values='completion_count'
  )
- ForecastPipe.forecast_by_category(
    categories=['Compliance', 'Technical', 'Leadership', 'Certification'],
    method='prophet',
    horizon=4  # 4 quarters
  )
- JoinPipe.join(training_costs, on=training_type)
- TransformPipe.calculate_budget(
    completions * avg_cost_per_completion
  )
- ForecastPipe.aggregate_forecasts(level='total')
- ForecastPipe.scenario_analysis(
    scenarios={
      'conservative': 0.9,
      'base': 1.0,
      'aggressive': 1.15
    }
  )
```

**Insights Generated:**
- Quarterly completion forecasts by training type
- Total forecasted completions and budget
- Budget breakdown by training category
- Scenario analysis: conservative, base, aggressive
- Recommended budget allocation
- Confidence intervals for planning

---

## 16. TREND ANALYSIS: Instructor Effectiveness Trends

**Natural Language Question:**
"Track how instructor effectiveness (measured by learner outcomes) has trended over time for instructor-led courses."

**Reasoning Plan:**
1. Join transcript_core with instructor assignments
2. Calculate instructor-level metrics by time period
3. Use TrendPipe.detect_trends() for each instructor
4. Use TrendPipe.identify_top_performers() based on trends
5. Use TrendPipe.detect_declining_performance() for early intervention

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_core, session_instructor, on=session_id)
- FilterPipe.filter(delivery_method='Instructor-Led')
- GroupByPipe.group_by([instructor_id, quarter])
- AggregatePipe.aggregate({
    'avg_completion_rate': 'mean(status == "Complete")',
    'avg_learner_score': 'mean(score)',
    'avg_satisfaction': 'mean(satisfaction_rating)',
    'session_count': 'count_distinct(session_id)',
    'learner_count': 'count_distinct(user_id)'
  })
- FilterPipe.filter(session_count >= 3)  # minimum sessions
- TrendPipe.detect_trends(
    group_by='instructor_id',
    metrics=['avg_completion_rate', 'avg_learner_score', 'avg_satisfaction']
  )
- TrendPipe.calculate_trend_strength()
- TrendPipe.identify_top_performers(
    metric='avg_learner_score',
    min_trend_strength=0.3
  )
- TrendPipe.detect_declining_performance(
    threshold=-0.2,
    consecutive_periods=2
  )
- RankPipe.rank_by([trend_strength, avg_learner_score])
```

**Insights Generated:**
- Trend direction and strength for each instructor
- Instructors with improving performance
- Instructors with declining performance (early warning)
- Top performers with positive trends
- Recommended actions: recognition, coaching, intervention
- Comparative benchmarking

---

## 17. RISK SCORING: Mandatory Training Compliance Risk

**Natural Language Question:**
"Calculate organization-wide compliance risk for mandatory training, identifying which organizational units are most at risk of failing audit requirements."

**Reasoning Plan:**
1. Identify mandatory training from training_requirement_tag
2. Calculate compliance metrics by organizational unit
3. Use RiskPipe.calculate_risk_scores() with compliance-specific weights
4. Use RiskPipe.calculate_time_to_compliance() for remediation planning
5. Use AnomalyPipe.flag_critical_violations() for immediate escalation

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(training_requirement_tag, transcript_assignment_core, on=training_id)
- FilterPipe.filter(is_mandatory=True)
- JoinPipe.join(user_ou_core, on=user_id)
- JoinPipe.join(transcript_core, on=assignment_id, how='left')
- GroupByPipe.group_by([ou_id, requirement_id])
- AggregatePipe.aggregate({
    'total_required': 'count(user_id)',
    'completed': 'sum(status == "Complete")',
    'in_progress': 'sum(status == "In Progress")',
    'not_started': 'sum(status IS NULL)',
    'overdue': 'sum(due_dt < current_date AND status != "Complete")',
    'critical_overdue': 'sum(days_overdue > 30)',
    'compliance_rate': 'completed / total_required'
  })
- RiskPipe.calculate_risk_scores(
    weights={
      'compliance_rate': -0.50,  # higher compliance = lower risk
      'overdue_rate': 0.30,
      'critical_overdue_rate': 0.20
    }
  )
- RiskPipe.normalize_scores(method='min_max', scale=[0, 100])
- AnomalyPipe.flag_critical_violations(
    conditions=['compliance_rate < 0.80', 'critical_overdue > 0']
  )
- RiskPipe.calculate_time_to_compliance(
    target_compliance=0.95,
    historical_velocity='avg_weekly_completions'
  )
- RankPipe.rank_by([risk_score, critical_overdue])
```

**Insights Generated:**
- Compliance risk score (0-100) per organizational unit
- Units in critical non-compliance (red flag)
- Time-to-compliance estimates
- Required completion velocity to meet deadlines
- Escalation recommendations
- Audit readiness assessment

---

## 18. ANOMALY DETECTION: Unusual Scoring Patterns

**Natural Language Question:**
"Detect courses or assessment instances with unusual score distributions that might indicate issues with content, grading, or cheating."

**Reasoning Plan:**
1. Analyze score distributions from transcript_core by course and session
2. Use AnomalyPipe.detect_distribution_anomalies() for statistical tests
3. Use AnomalyPipe.detect_outlier_groups() for clusters of similar anomalies
4. Use StatsPipe.test_distribution_normality() for validation
5. Flag for investigation based on anomaly severity

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_core, training_core, on=training_id)
- FilterPipe.filter(status='Complete' AND score IS NOT NULL)
- GroupByPipe.group_by([training_id, session_id])
- AggregatePipe.aggregate({
    'score_mean': 'mean(score)',
    'score_median': 'median(score)',
    'score_std': 'std(score)',
    'score_min': 'min(score)',
    'score_max': 'max(score)',
    'learner_count': 'count(user_id)',
    'perfect_score_pct': 'mean(score == 100)',
    'failing_score_pct': 'mean(score < 70)'
  })
- FilterPipe.filter(learner_count >= 10)  # minimum sample
- StatsPipe.test_distribution_normality(method='shapiro')
- AnomalyPipe.detect_distribution_anomalies(
    reference_metric='score_mean',
    expected_distribution='normal',
    significance=0.05
  )
- AnomalyPipe.detect_outlier_groups(
    metrics=['score_mean', 'score_std', 'perfect_score_pct'],
    method='dbscan'
  )
- TransformPipe.calculate_anomaly_severity(
    factors=['deviation_magnitude', 'affected_learners', 'anomaly_type']
  )
- FilterPipe.filter(anomaly_severity >= 0.6)
- RankPipe.rank_by(anomaly_severity, ascending=False)
```

**Insights Generated:**
- Courses/sessions with anomalous score distributions
- Anomaly types: too easy, too hard, bimodal, suspicious uniformity
- Statistical test results (p-values, normality tests)
- Potential causes: content issues, grading errors, cheating
- Severity scores for prioritization
- Recommended investigations

---

## 19. SEGMENTATION: Learning Style Profiling

**Natural Language Question:**
"Segment learners based on their preferred learning modalities, pace, and content types to personalize learning recommendations."

**Reasoning Plan:**
1. Aggregate learner preferences from transcript_core and training_core
2. Analyze completion patterns by delivery_method, training_type, duration
3. Use SegmentPipe.perform_clustering() to identify learning style personas
4. Use SegmentPipe.profile_segments() to characterize each style
5. Use RecommenderPipe to suggest personalized content

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(transcript_core, training_core, on=training_id)
- FilterPipe.filter(status='Complete')
- GroupByPipe.group_by(user_id)
- AggregatePipe.aggregate({
    'prefers_video': 'mean(delivery_method == "Video")',
    'prefers_classroom': 'mean(delivery_method == "Instructor-Led")',
    'prefers_elearning': 'mean(delivery_method == "E-Learning")',
    'avg_course_hours': 'mean(training_hours)',
    'prefers_short_courses': 'mean(training_hours < 2)',
    'prefers_long_courses': 'mean(training_hours > 8)',
    'completion_speed': 'mean(completion_time_days / training_hours)',
    'prefers_technical': 'mean(training_type == "Technical")',
    'prefers_soft_skills': 'mean(training_type == "Soft Skills")',
    'weekend_learner': 'mean(weekday(completed_dt) IN [6,7])',
    'evening_learner': 'mean(hour(last_activity) >= 17)'
  })
- SegmentPipe.find_optimal_segments(method='silhouette', max_k=8)
- SegmentPipe.perform_clustering(
    method='kmeans',
    n_clusters=5,
    features=['prefers_video', 'completion_speed', 'prefers_short_courses', 
              'prefers_technical', 'weekend_learner']
  )
- SegmentPipe.profile_segments()
- SegmentPipe.label_segments(
    method='auto',
    naming_convention='descriptive'
  )
```

**Insights Generated:**
- 5 learning style personas:
  * "Visual Fast Learners" - prefer videos, complete quickly
  * "Classroom Traditionalists" - prefer instructor-led, steady pace
  * "Weekend Warriors" - study outside work hours, prefer self-paced
  * "Technical Deep-Divers" - prefer long technical courses, thorough
  * "Bite-Size Learners" - prefer short courses, frequent completions
- Profile characteristics for each persona
- Recommended content types per persona
- Optimal delivery methods per persona
- Personalization strategies

---

## 20. FORECAST: Skill Gap Closure Timeline

**Natural Language Question:**
"Forecast how long it will take to close identified skill gaps across the organization based on current training velocity and enrollment patterns."

**Reasoning Plan:**
1. Identify skill gaps from user skills assessments
2. Map required training to close each gap
3. Use historical completion rates to estimate velocity
4. Use ForecastPipe.forecast_completion() with constraints
5. Use ForecastPipe.scenario_analysis() for different intervention levels
6. Generate timeline and resource requirements

**Answer:**
```
Pipeline Flow:
- JoinPipe.join(UserSkillMap, UserSkills, on=user_id)
- FilterPipe.filter(current_skill_level < required_skill_level)
- JoinPipe.join(skill_training_map, on=skill_id)
- JoinPipe.join(transcript_assignment_core, on=[user_id, training_id], how='left')
- GroupByPipe.group_by([skill_id, training_id])
- AggregatePipe.aggregate({
    'users_needing_training': 'count_distinct(user_id)',
    'users_enrolled': 'count_distinct(CASE WHEN assignment_id IS NOT NULL)',
    'users_completed': 'count_distinct(CASE WHEN status == "Complete")',
    'gap_size': 'users_needing_training - users_completed',
    'avg_completion_time': 'mean(completion_time_days)'
  })
- JoinPipe.join(historical_velocity, on=training_id)
- TransformPipe.calculate_required_capacity(
    gap_size / weekly_completion_rate
  )
- ForecastPipe.forecast_completion(
    current_velocity='weekly_completion_rate',
    remaining_gap='gap_size',
    constraints=['instructor_capacity', 'seat_availability']
  )
- ForecastPipe.scenario_analysis(
    scenarios={
      'current_pace': 1.0,
      'with_initiatives': 1.5,
      'aggressive_push': 2.0
    }
  )
- RankPipe.rank_by([gap_size, estimated_months_to_close])
```

**Insights Generated:**
- Skill gaps ranked by size and urgency
- Current completion velocity per skill/course
- Estimated time to close each gap at current pace
- Scenario forecasts:
  * Current pace: X months to close 90% of gaps
  * With initiatives: Y months (faster hiring/enrollment)
  * Aggressive: Z months (maximum resources)
- Resource bottlenecks and constraints
- Recommended action plan with milestones
- ROI projections for acceleration initiatives

---

## Summary

These 20 use cases demonstrate how to combine:

**Data Models:**
- users_core, transcript_core, training_core, transcript_assignment_core
- address_core, user_ou_core, training_requirement_tag
- Session and instructor data

**Analytical Pipes:**
- **TrendPipe**: Time series trends, change detection, period comparisons
- **SegmentPipe**: Clustering, profiling, segment comparison
- **AnomalyPipe**: Outlier detection, pattern anomalies, distribution testing
- **ForecastPipe**: Forecasting, scenario analysis, prediction intervals
- **RiskPipe**: Risk scoring, survival analysis, predictive modeling
- **CohortPipe**: Retention, conversion, LTV analysis
- **FunnelPipe**: Funnel analysis, path analysis

**Analysis Types:**
- Trend Analysis (6 examples)
- Risk Scoring (4 examples)
- Anomaly Detection (4 examples)
- Segmentation (4 examples)
- Forecasting (4 examples)

Each example provides a complete analytical workflow from data preparation through insight generation, demonstrating the power of combining these pipeline functions with rich learning management data.
