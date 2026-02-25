#!/usr/bin/env node
/**
 * SQL Function Examples Generator
 * Generates 100+ examples across: Asset Management, Application Security,
 * Cornerstone Talent, Cornerstone Learning
 *
 * Run: node generate_examples.js
 * Output: sql_function_examples_expanded.json
 */

const fs = require('fs');
const path = require('path');

// Load existing examples as base (exclude previously generated to avoid duplicates)
const existingPath = path.join(__dirname, 'sql_function_examples.json');
const existing = JSON.parse(fs.readFileSync(existingPath, 'utf8'));
const baseExamples = existing.examples.filter(e => !String(e.id || '').startsWith('gen.'));

// Domain templates: each entry produces one or more examples
const DOMAIN_TEMPLATES = [
  // === ASSET MANAGEMENT ===
  { domain: 'Asset Management', metric: 'asset_count', table: 'asset_inventory_daily', dim: 'department', q: 'Which metrics correlated when our asset count dropped sharply?', fn: 'find_correlated_metrics' },
  { domain: 'Asset Management', metric: 'depreciation_value', table: 'asset_financials_daily', dim: 'asset_class', q: 'Which asset classes contributed most to the depreciation anomaly?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Asset Management', metric: 'compliance_gap_count', table: 'asset_compliance_daily', dim: 'region', q: 'Does compliance gap count lead asset remediation backlog increases?', fn: 'calculate_lag_correlation' },
  { domain: 'Asset Management', metric: 'asset_count', table: 'asset_inventory_daily', dim: 'region', q: 'Assemble full context for the asset count anomaly for reporting.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Asset Management', metric: 'criticality', param: 'asset_criticality', q: 'Score impact of losing a critical datacenter asset.', fn: 'calculate_impact_from_json' },
  { domain: 'Asset Management', metric: 'asset_id', table: 'asset_inventory', q: 'Batch-score impact across 50 assets for prioritization.', fn: 'calculate_impact_batch' },
  { domain: 'Asset Management', metric: 'blast_radius', q: 'A core switch failure affects 25 downstream systems. Estimate blast radius.', fn: 'calculate_cascading_impact' },
  { domain: 'Asset Management', metric: 'overall_impact', q: 'Given asset impact score 72.4, what action tier?', fn: 'classify_impact_level' },
  { domain: 'Asset Management', metric: 'end_of_life_count', table: 'asset_lifecycle_daily', q: 'What is breach likelihood for an EOL server with 4 critical vulns?', fn: 'calculate_vulnerability_likelihood' },
  { domain: 'Asset Management', metric: 'patch_lag_days', table: 'asset_patch_status', q: 'CVE present 60 days, SLA in 3 days. Time-weighted likelihood?', fn: 'calculate_time_weighted_likelihood' },
  { domain: 'Asset Management', metric: 'asset_id', table: 'asset_risk_scores', q: 'Is asset db-01 breach likelihood trending up over 90 days?', fn: 'calculate_likelihood_trend' },
  { domain: 'Asset Management', metric: 'maintenance_cost', table: 'asset_costs_daily', q: 'Smooth 7-day maintenance cost and flag spikes.', fn: 'calculate_sma' },
  { domain: 'Asset Management', metric: 'utilization_pct', table: 'asset_utilization_daily', q: 'Bollinger Bands on asset utilization to spot outliers.', fn: 'calculate_bollinger_bands' },
  { domain: 'Asset Management', metric: 'fail_count', table: 'asset_failures_daily', q: 'Does utilization lead failure count? Rolling correlation.', fn: 'calculate_moving_correlation' },
  { domain: 'Asset Management', metric: 'maintenance_hours', table: 'asset_maintenance_events', q: 'Does maintenance hour count show weekly seasonality?', fn: 'calculate_autocorrelation' },
  { domain: 'Asset Management', metric: 'health_score', table: 'asset_health_daily', q: 'Is asset health score series stationary before forecasting?', fn: 'test_stationarity' },
  { domain: 'Asset Management', metric: 'repair_time_hours', table: 'asset_repairs', dim: 'asset_class', q: 'Compare repair time distribution across asset classes.', fn: 'analyze_distribution' },
  { domain: 'Asset Management', metric: 'eol_count', table: 'asset_lifecycle_daily', q: 'Is EOL asset count trending up over the quarter?', fn: 'calculate_statistical_trend' },
  { domain: 'Asset Management', metric: 'acquisition_cost', table: 'asset_purchases_daily', q: 'Forecast asset acquisition spend for next 30 days.', fn: 'forecast_linear' },
  { domain: 'Asset Management', metric: 'failure_count', table: 'asset_failures_daily', q: 'Flag anomalous failure days in past 90 days.', fn: 'detect_anomalies' },
  { domain: 'Asset Management', metric: 'repair_requests', table: 'asset_repair_tickets', q: 'Does repair volume show day-of-week seasonality?', fn: 'detect_seasonality' },
  { domain: 'Asset Management', metric: 'repair_hours', table: 'asset_repairs', q: '95% CI for mean repair time across asset classes?', fn: 'calculate_bootstrap_ci' },
  { domain: 'Asset Management', metric: 'uptime_pct', table: 'asset_uptime_daily', dim: 'asset_group', q: 'After preventive maintenance rollout, did uptime improve by group?', fn: 'calculate_prepost_comparison' },
  { domain: 'Asset Management', metric: 'downtime_minutes', table: 'asset_downtime_events', q: 'Effect size of new monitoring tool on mean downtime?', fn: 'calculate_effect_sizes' },

  // === APPLICATION SECURITY ===
  { domain: 'Application Security', metric: 'sast_finding_count', table: 'sast_scan_results_daily', dim: 'app_id', q: 'SAST finding count spiked. Which other AppSec metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Application Security', metric: 'critical_findings', table: 'dast_scan_daily', dim: 'environment', q: 'Which environments contributed most to the finding spike?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Application Security', metric: 'dependency_vuln_count', table: 'sca_scan_daily', q: 'Does dependency vuln count lead SAST finding increases?', fn: 'calculate_lag_correlation' },
  { domain: 'Application Security', metric: 'secrets_exposed', table: 'secrets_scan_daily', q: 'Full payload for secrets exposure anomaly.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Application Security', metric: 'data_exposure', param: 'data_exposure_severity', q: 'Score impact of OWASP A01 broken access control in prod API.', fn: 'calculate_impact_from_json' },
  { domain: 'Application Security', metric: 'app_id', table: 'app_risk_scores', q: 'Batch impact across top 20 applications for remediation priority.', fn: 'calculate_impact_batch' },
  { domain: 'Application Security', metric: 'critical_findings', table: 'sast_findings', q: 'Likelihood for app with 6 critical SAST, 12 high, 3 in CISA KEV?', fn: 'calculate_vulnerability_likelihood' },
  { domain: 'Application Security', metric: 'open_finding_age', table: 'finding_age_tracking', q: 'Finding open 90 days, SLA in 7 days. Time-weighted likelihood?', fn: 'calculate_time_weighted_likelihood' },
  { domain: 'Application Security', metric: 'critical_count', table: 'sast_daily_summary', q: 'Smooth SAST critical count over 14 days and flag spikes.', fn: 'calculate_sma' },
  { domain: 'Application Security', metric: 'finding_count', table: 'dast_scan_results', q: 'Bollinger Bands on DAST finding count for risk periods.', fn: 'calculate_bollinger_bands' },
  { domain: 'Application Security', metric: 'sast_count', table: 'sast_daily', sec_metric: 'dast_count', table2: 'dast_daily', q: 'Is SAST-DAST finding relationship changing over time?', fn: 'calculate_moving_correlation' },
  { domain: 'Application Security', metric: 'scan_fail_count', table: 'scan_schedule_daily', q: 'Does scan failure count show weekly periodicity?', fn: 'calculate_autocorrelation' },
  { domain: 'Application Security', metric: 'remediation_days', table: 'finding_remediation_tickets', dim: 'severity', q: 'Compare remediation time distribution by severity.', fn: 'analyze_distribution' },
  { domain: 'Application Security', metric: 'critical_count', table: 'sast_daily_summary', q: 'Is critical SAST finding count trending down?', fn: 'calculate_statistical_trend' },
  { domain: 'Application Security', metric: 'open_critical', table: 'finding_backlog_daily', q: 'Forecast open critical findings in 30 days.', fn: 'forecast_linear' },
  { domain: 'Application Security', metric: 'new_findings', table: 'sast_scan_results', q: 'Flag anomalous new finding discovery days.', fn: 'detect_anomalies' },
  { domain: 'Application Security', metric: 'scan_volume', table: 'scan_execution_log', q: 'Does scan volume show day-of-week seasonality?', fn: 'detect_seasonality' },
  { domain: 'Application Security', metric: 'remediation_hours', table: 'finding_remediation', q: '95% CI for mean time-to-remediate critical findings?', fn: 'calculate_bootstrap_ci' },
  { domain: 'Application Security', metric: 'fix_rate', table: 'finding_remediation_by_app', dim: 'app_id', q: 'After SAST integration rollout, did fix rate improve by app?', fn: 'calculate_prepost_comparison' },
  { domain: 'Application Security', metric: 'resolution_time', table: 'finding_resolution', q: 'Effect size of new SAST tool on resolution time?', fn: 'calculate_effect_sizes' },
  { domain: 'Application Security', metric: 'percent_change', table: 'waf_block_rate_daily', q: 'Did new WAF ruleset reduce block rate vs control?', fn: 'calculate_percent_change_comparison' },

  // === CORNERSTONE LEARNING ===
  { domain: 'Cornerstone Learning', metric: 'enrollment_count', table: 'transcript_core', dim: 'department', q: 'Enrollment dropped. Which other learning metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Cornerstone Learning', metric: 'completion_rate', table: 'transcript_core', dim: 'course_category', q: 'Which course categories drove the completion rate drop?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Learning', metric: 'completion_rate', table: 'transcript_core', sec_metric: 'enrollment_count', q: 'Does enrollment lead completion rate changes?', fn: 'calculate_lag_correlation' },
  { domain: 'Cornerstone Learning', metric: 'completion_count', table: 'transcript_core', q: 'Full context for enrollment anomaly for L&D report.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Cornerstone Learning', metric: 'completion_risk', param: 'dropout_risk', q: 'Score impact of 500 learners at high dropout risk.', fn: 'calculate_impact_from_json' },
  { domain: 'Cornerstone Learning', metric: 'course_id', table: 'training_core', q: 'Batch non-completion risk across 30 critical courses.', fn: 'calculate_impact_batch' },
  { domain: 'Cornerstone Learning', metric: 'completion_days', table: 'transcript_core', dim: 'department', q: 'Smooth 7-day completion volume and flag anomalies.', fn: 'calculate_sma' },
  { domain: 'Cornerstone Learning', metric: 'enrollment_count', table: 'transcript_core', q: 'Bollinger Bands on daily enrollment for unusual days.', fn: 'calculate_bollinger_bands' },
  { domain: 'Cornerstone Learning', metric: 'completion_rate', table: 'transcript_core', dim: 'course_id', q: 'Compare completion time distribution by course.', fn: 'analyze_distribution' },
  { domain: 'Cornerstone Learning', metric: 'enrollment_count', table: 'transcript_core', q: 'Is course enrollment trending up or down this quarter?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Learning', metric: 'completion_volume', table: 'transcript_core', q: 'Forecast training completion volume for next 30 days.', fn: 'forecast_linear' },
  { domain: 'Cornerstone Learning', metric: 'dropout_count', table: 'transcript_core', q: 'Flag days with anomalous dropout rates.', fn: 'detect_anomalies' },
  { domain: 'Cornerstone Learning', metric: 'enrollment_count', table: 'transcript_core', q: 'Does enrollment show day-of-week or monthly seasonality?', fn: 'detect_seasonality' },
  { domain: 'Cornerstone Learning', metric: 'completion_days', table: 'transcript_core', q: '95% CI for mean time-to-complete mandatory courses?', fn: 'calculate_bootstrap_ci' },
  { domain: 'Cornerstone Learning', metric: 'completion_rate', table: 'transcript_core', dim: 'department', q: 'After LMS redesign, did completion rates improve by department?', fn: 'calculate_prepost_comparison' },
  { domain: 'Cornerstone Learning', metric: 'score', table: 'transcript_core', dim: 'course_id', q: 'Effect size of new course format on learner scores?', fn: 'calculate_effect_sizes' },
  { domain: 'Cornerstone Learning', metric: 'pass_rate', table: 'transcript_core', q: 'Did new assessment format improve pass rate vs control?', fn: 'calculate_percent_change_comparison' },
  { domain: 'Cornerstone Learning', metric: 'cert_expiring_count', table: 'transcript_core', q: 'Trend in certifications expiring in next 90 days?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Learning', metric: 'skill_gap_count', table: 'UserSkillMap', dim: 'department', q: 'Which departments have largest skill gaps?', fn: 'decompose_impact_by_dimension' },

  // === CORNERSTONE TALENT ===
  { domain: 'Cornerstone Talent', metric: 'goal_completion_rate', table: 'goal_tracking_daily', dim: 'department', q: 'Goal completion dropped. Which talent metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Cornerstone Talent', metric: 'performance_rating', table: 'performance_reviews', dim: 'manager_id', q: 'Which managers contributed most to rating distribution shift?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Talent', metric: 'turnover_count', table: 'turnover_daily', sec_metric: 'engagement_score', q: 'Does engagement score lead turnover changes?', fn: 'calculate_lag_correlation' },
  { domain: 'Cornerstone Talent', metric: 'engagement_score', table: 'engagement_survey_results', q: 'Full context for engagement anomaly for HR report.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Cornerstone Talent', metric: 'flight_risk', param: 'flight_risk_score', q: 'Score impact of losing top 20 performers.', fn: 'calculate_impact_from_json' },
  { domain: 'Cornerstone Talent', metric: 'employee_id', table: 'succession_candidates', q: 'Batch flight risk across high-potential employees.', fn: 'calculate_impact_batch' },
  { domain: 'Cornerstone Talent', metric: 'rating_count', table: 'performance_review_daily', q: 'Smooth 7-day review volume and flag spikes.', fn: 'calculate_sma' },
  { domain: 'Cornerstone Talent', metric: 'turnover_rate', table: 'turnover_daily', q: 'Bollinger Bands on voluntary turnover rate.', fn: 'calculate_bollinger_bands' },
  { domain: 'Cornerstone Talent', metric: 'review_score', table: 'performance_reviews', dim: 'department', q: 'Compare rating distribution across departments.', fn: 'analyze_distribution' },
  { domain: 'Cornerstone Talent', metric: 'turnover_count', table: 'turnover_daily', q: 'Is voluntary turnover trending up or down?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Talent', metric: 'headcount', table: 'headcount_daily', q: 'Forecast headcount for next 30 days.', fn: 'forecast_linear' },
  { domain: 'Cornerstone Talent', metric: 'resignation_count', table: 'turnover_daily', q: 'Flag anomalous automatic resignation days.', fn: 'detect_anomalies' },
  { domain: 'Cornerstone Talent', metric: 'review_count', table: 'performance_review_daily', q: 'Does review volume show quarterly seasonality?', fn: 'detect_seasonality' },
  { domain: 'Cornerstone Talent', metric: 'time_to_fill_days', table: 'recruitment_metrics', q: '95% CI for mean time-to-fill by role family?', fn: 'calculate_bootstrap_ci' },
  { domain: 'Cornerstone Talent', metric: 'engagement_score', table: 'engagement_survey', dim: 'department', q: 'After engagement initiative, did scores improve by department?', fn: 'calculate_prepost_comparison' },
  { domain: 'Cornerstone Talent', metric: '9box_score', table: 'performance_9box', q: 'Effect size of new calibration process on ratings?', fn: 'calculate_effect_sizes' },
  { domain: 'Cornerstone Talent', metric: 'promotion_rate', table: 'promotion_events', q: 'Did new promotion criteria change promotion rate vs control?', fn: 'calculate_percent_change_comparison' },
  { domain: 'Cornerstone Talent', metric: 'succession_readiness', table: 'succession_planning', q: 'Trend in succession readiness for critical roles?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Talent', metric: 'skill_coverage', table: 'UserSkillMap', dim: 'role', q: 'Which roles have largest skill coverage gaps?', fn: 'decompose_impact_by_dimension' },

  // === ADDITIONAL VARIATIONS (50+ more to reach 100+) ===
  { domain: 'Asset Management', metric: 'warranty_expiring_count', table: 'asset_warranty_daily', q: 'Which regions have most warranty expirations driving the spike?', fn: 'decompose_impact_by_dimension', dim: 'region' },
  { domain: 'Asset Management', metric: 'software_license_count', table: 'license_inventory_daily', q: 'License count anomaly — full context for audit report.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Asset Management', metric: 'cost_per_asset', table: 'asset_costs_daily', dim: 'asset_type', q: 'Compare cost-per-asset distribution across asset types.', fn: 'analyze_distribution' },
  { domain: 'Asset Management', metric: 'network_device_count', table: 'network_inventory_daily', q: 'Is network device count trending up?', fn: 'calculate_statistical_trend' },
  { domain: 'Asset Management', metric: 'cloud_cost', table: 'cloud_spend_daily', q: 'Forecast cloud spend for next 30 days.', fn: 'forecast_linear' },

  { domain: 'Application Security', metric: 'owasp_a01_count', table: 'owasp_scan_daily', dim: 'app_tier', q: 'Which app tiers contributed most to OWASP A01 spike?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Application Security', metric: 'license_violation_count', table: 'license_scan_daily', q: 'License violation spike — full payload for security report.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Application Security', metric: 'xss_finding_count', table: 'dast_xss_results', dim: 'url_path', q: 'Compare XSS finding count distribution by URL path.', fn: 'analyze_distribution' },
  { domain: 'Application Security', metric: 'sbom_vuln_count', table: 'sbom_scan_daily', q: 'Is SBOM vulnerability count trending down?', fn: 'calculate_statistical_trend' },
  { domain: 'Application Security', metric: 'pentest_finding_count', table: 'pentest_results', q: 'Forecast open pentest findings in 60 days.', fn: 'forecast_linear' },
  { domain: 'Application Security', metric: 'injection_findings', table: 'sast_injection_results', q: 'Correlation: injection findings vs SQLi-specific count?', fn: 'find_correlated_metrics' },
  { domain: 'Application Security', metric: 'api_security_score', table: 'api_security_scans', q: 'Test stationarity of API security score before forecasting.', fn: 'test_stationarity' },
  { domain: 'Application Security', metric: 'container_vuln_count', table: 'container_scan_daily', q: 'Bollinger Bands on container vuln count.', fn: 'calculate_bollinger_bands' },

  { domain: 'Cornerstone Learning', metric: 'assignment_response_hours', table: 'transcript_assignment_core', dim: 'course_id', q: 'Which courses had slowest assignment response times?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Learning', metric: 'first_attempt_pass_rate', table: 'transcript_core', q: 'Pass rate dropped. Which learning metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Cornerstone Learning', metric: 'assessment_score', table: 'transcript_core', dim: 'instructor_id', q: 'Compare assessment score distribution by instructor.', fn: 'analyze_distribution' },
  { domain: 'Cornerstone Learning', metric: 'mandatory_completion_pct', table: 'training_requirement_tag', q: 'Is mandatory completion % trending up?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Learning', metric: 'learning_path_completion', table: 'training_core', q: 'Forecast learning path completion volume.', fn: 'forecast_linear' },
  { domain: 'Cornerstone Learning', metric: 'course_rating', table: 'rating_core', dim: 'course_category', q: 'Which categories drove the rating drop?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Learning', metric: 'time_in_course_minutes', table: 'transcript_core', q: 'Flag courses with suspiciously fast completion times.', fn: 'detect_anomalies' },
  { domain: 'Cornerstone Learning', metric: 'instructor_effectiveness', table: 'session_instructor', q: 'Does instructor effectiveness show term seasonality?', fn: 'detect_seasonality' },

  { domain: 'Cornerstone Talent', metric: 'calibration_deviation', table: 'performance_calibration', dim: 'manager_id', q: 'Which managers contributed most to calibration deviation?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Talent', metric: 'internal_mobility_rate', table: 'mobility_events', q: 'Mobility rate dropped. Which talent metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Cornerstone Talent', metric: 'offer_acceptance_rate', table: 'recruitment_metrics', dim: 'job_family', q: 'Compare offer acceptance distribution by job family.', fn: 'analyze_distribution' },
  { domain: 'Cornerstone Talent', metric: 'training_hours_per_employee', table: 'training_hours_daily', q: 'Is training hours per employee trending up?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Talent', metric: 'open_positions', table: 'headcount_daily', q: 'Forecast open positions for next quarter.', fn: 'forecast_linear' },
  { domain: 'Cornerstone Talent', metric: 'goal_progress_pct', table: 'goal_tracking_daily', q: 'Goal progress anomaly — full context for HR.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Cornerstone Talent', metric: 'high_potential_count', table: 'succession_planning', q: 'Flag anomalous high-potential identification days.', fn: 'detect_anomalies' },
  { domain: 'Cornerstone Talent', metric: 'promotion_count', table: 'promotion_events', q: 'Does promotion count show fiscal year seasonality?', fn: 'detect_seasonality' },

  // Cross-domain variations
  { domain: 'Vulnerability Management', metric: 'epss_score', table: 'cve_epss_daily', q: 'EPSS score spiked. Which vuln metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Vulnerability Management', metric: 'mean_time_to_patch', table: 'patch_velocity_daily', dim: 'asset_group', q: 'Which asset groups drive slowest patch velocity?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Compliance', metric: 'control_failure_count', table: 'compliance_scan_daily', dim: 'control_family', q: 'Which control families contributed most to failure spike?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Compliance', metric: 'audit_finding_count', table: 'audit_findings_daily', q: 'Audit finding spike — full context for audit committee.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Compliance', metric: 'policy_violation_count', table: 'policy_violations_daily', q: 'Is policy violation count trending down?', fn: 'calculate_statistical_trend' },
  { domain: 'Compliance', metric: 'remediation_backlog', table: 'compliance_remediation', q: '95% CI for mean time-to-remediate control failures?', fn: 'calculate_bootstrap_ci' },
  { domain: 'Compliance', metric: 'compliance_score', table: 'compliance_scores_daily', dim: 'region', q: 'After control rollout, did compliance scores improve by region?', fn: 'calculate_prepost_comparison' },

  { domain: 'Asset Management', metric: 'discovery_count', table: 'asset_discovery_daily', q: 'Flag anomalous asset discovery days.', fn: 'detect_anomalies' },
  { domain: 'Asset Management', metric: 'purchase_order_count', table: 'asset_purchases_daily', q: 'Does procurement volume show quarterly seasonality?', fn: 'detect_seasonality' },
  { domain: 'Application Security', metric: 'false_positive_rate', table: 'sast_triage_daily', q: 'After SAST tuning, did false positive rate decrease?', fn: 'calculate_prepost_comparison', dim: 'tool' },
  { domain: 'Application Security', metric: 'code_coverage_pct', table: 'sast_scan_metadata', q: 'Effect size of new SAST tool on code coverage?', fn: 'calculate_effect_sizes' },
  { domain: 'Cornerstone Learning', metric: 'course_difficulty_score', table: 'training_core', q: 'Compare course difficulty distribution across categories.', fn: 'analyze_distribution', dim: 'training_type_core' },
  { domain: 'Cornerstone Learning', metric: 'learner_satisfaction', table: 'rating_core', q: 'Does satisfaction show post-training survey seasonality?', fn: 'detect_seasonality' },
  { domain: 'Cornerstone Talent', metric: 'regrettable_attrition_count', table: 'turnover_daily', q: 'Flag anomalous regrettable attrition days.', fn: 'detect_anomalies' },
  { domain: 'Cornerstone Talent', metric: 'diversity_index', table: 'diversity_metrics_daily', q: 'Effect size of D&I initiative on diversity index?', fn: 'calculate_effect_sizes' },

  // === MORE TO REACH 200+ ===
  { domain: 'Asset Management', metric: 'cmdb_sync_lag_hours', table: 'cmdb_sync_daily', q: 'Correlation: CMDB sync lag vs discovery count?', fn: 'find_correlated_metrics' },
  { domain: 'Asset Management', metric: 'tco_per_asset', table: 'asset_tco_daily', dim: 'location', q: 'Which locations drive highest TCO anomaly?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Asset Management', metric: 'rogue_asset_count', table: 'rogue_detection_daily', q: 'Rogue asset spike — full context.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Asset Management', metric: 'scan_coverage_pct', table: 'asset_scan_daily', q: 'Bollinger Bands on scan coverage %.', fn: 'calculate_bollinger_bands' },
  { domain: 'Asset Management', metric: 'lifecycle_stage_count', table: 'asset_lifecycle_daily', dim: 'stage', q: 'Compare asset count distribution by lifecycle stage.', fn: 'analyze_distribution' },

  { domain: 'Application Security', metric: 'critical_cwe_count', table: 'sast_cwe_daily', dim: 'cwe_category', q: 'Which CWE categories drive most critical findings?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Application Security', metric: 'runtime_finding_count', table: 'iast_scan_daily', q: 'IAST finding spike — full payload.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Application Security', metric: 'mttr_hours', table: 'finding_remediation', dim: 'owasp_category', q: 'Compare MTTR distribution by OWASP category.', fn: 'analyze_distribution' },
  { domain: 'Application Security', metric: 'security_test_coverage', table: 'test_coverage_daily', q: 'Is security test coverage trending up?', fn: 'calculate_statistical_trend' },
  { domain: 'Application Security', metric: 'supply_chain_risk_score', table: 'sbom_risk_daily', q: 'Forecast supply chain risk score.', fn: 'forecast_linear' },

  { domain: 'Cornerstone Learning', metric: 'course_views_count', table: 'content_analytics_daily', dim: 'content_type', q: 'Which content types drove view count spike?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Learning', metric: 'learning_hours', table: 'transcript_core', dim: 'department', q: 'Compare learning hours distribution by department.', fn: 'analyze_distribution' },
  { domain: 'Cornerstone Learning', metric: 'instructor_rating', table: 'session_instructor', dim: 'course_category', q: 'Which categories drove instructor rating drop?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Learning', metric: 'withdrawal_rate', table: 'transcript_core', q: 'Is withdrawal rate trending down?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Learning', metric: 'skill_assessment_score', table: 'UserSkillMap', q: 'Forecast skill assessment completions.', fn: 'forecast_linear' },

  { domain: 'Cornerstone Talent', metric: 'compensation_ratio', table: 'comp_analytics_daily', dim: 'job_level', q: 'Which job levels drive compensation ratio anomaly?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Talent', metric: 'feedback_response_rate', table: 'feedback_survey_daily', q: 'Feedback response dropped. Which talent metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Cornerstone Talent', metric: 'performance_improvement_pct', table: 'performance_reviews', dim: 'department', q: 'Compare performance improvement distribution.', fn: 'analyze_distribution' },
  { domain: 'Cornerstone Talent', metric: 'learning_hours_per_fte', table: 'training_hours_daily', q: 'Is learning hours per FTE trending up?', fn: 'calculate_statistical_trend' },
  { domain: 'Cornerstone Talent', metric: 'succession_coverage_pct', table: 'succession_planning', q: 'Forecast succession coverage for critical roles.', fn: 'forecast_linear' },

  { domain: 'Vulnerability Management', metric: 'remediation_velocity', table: 'patch_velocity_daily', q: 'Is remediation velocity trending up?', fn: 'calculate_statistical_trend' },
  { domain: 'Vulnerability Management', metric: 'exposure_score', table: 'asset_exposure_daily', dim: 'asset_group', q: 'Which asset groups drive exposure score spike?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Compliance', metric: 'control_gap_count', table: 'compliance_assessment_daily', q: 'Control gap spike — full context.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Compliance', metric: 'certification_renewal_count', table: 'certification_tracking', q: 'Forecast certification renewals due next quarter.', fn: 'forecast_linear' },
  { domain: 'Asset Management', metric: 'sensor_alert_count', table: 'iot_sensor_daily', q: 'Sensor alert spike — which metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Asset Management', metric: 'power_consumption_kwh', table: 'asset_power_daily', dim: 'datacenter', q: 'Which datacenters drive power consumption anomaly?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Application Security', metric: 'api_auth_failure_count', table: 'api_security_logs', q: 'API auth failure spike — full context.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Application Security', metric: 'csrf_finding_count', table: 'dast_csrf_results', dim: 'endpoint', q: 'Which endpoints drive CSRF finding spike?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Learning', metric: 'certification_attempt_count', table: 'transcript_core', q: 'Cert attempt spike — which learning metrics correlated?', fn: 'find_correlated_metrics' },
  { domain: 'Cornerstone Learning', metric: 'social_learning_engagement', table: 'content_interactions_daily', dim: 'content_format', q: 'Which formats drive engagement drop?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Cornerstone Talent', metric: 'voluntary_turnover_pct', table: 'turnover_daily', q: 'Voluntary turnover spike — full context for HR.', fn: 'build_anomaly_explanation_payload' },
  { domain: 'Cornerstone Talent', metric: 'performance_distribution_shift', table: 'performance_reviews', dim: 'business_unit', q: 'Which BUs drive rating distribution shift?', fn: 'decompose_impact_by_dimension' },
  { domain: 'Vulnerability Management', metric: 'cve_age_days', table: 'cve_inventory', dim: 'severity', q: 'Compare CVE age distribution by severity.', fn: 'analyze_distribution' },
  { domain: 'Compliance', metric: 'audit_preparedness_score', table: 'audit_readiness_daily', q: 'Is audit preparedness trending up?', fn: 'calculate_statistical_trend' },
  { domain: 'Asset Management', metric: 'vendor_risk_score', table: 'vendor_assessments', q: 'Batch vendor risk across top 50 suppliers.', fn: 'calculate_impact_batch' },
  { domain: 'Cornerstone Learning', metric: 'course_material_update_impact', table: 'transcript_core', dim: 'course_id', q: 'After content update, did completion improve by course?', fn: 'calculate_prepost_comparison' },
  { domain: 'Cornerstone Talent', metric: 'new_hire_productivity', table: 'onboarding_metrics', q: 'Effect size of new onboarding program on productivity?', fn: 'calculate_effect_sizes' },
];

// Base SQL templates per function (simplified - actual SQL varies by metric/table)
const SQL_TEMPLATES = {
  find_correlated_metrics: (m, t) => `SELECT metric_pair, correlated_metric, correlation, direction, data_points\nFROM find_correlated_metrics('${m}', '2024-01-15'::DATE, 14, 0.60)\nORDER BY abs_correlation DESC;`,
  decompose_impact_by_dimension: (m, t, d) => `SELECT dimension_value, baseline_avg, anomaly_actual, absolute_delta, contribution_to_total, impact_rank\nFROM decompose_impact_by_dimension('${m}', '2024-01-15'::DATE, '${d || 'region_tier'}', 7, 1)\nORDER BY impact_rank;`,
  calculate_lag_correlation: (m, s) => `SELECT lag_periods, lag_direction, correlation, interpretation\nFROM calculate_lag_correlation('${m}', '${s || 'p99_latency_ms'}', '2024-01-15'::DATE, 14, 5)\nORDER BY abs_correlation DESC LIMIT 5;`,
  build_anomaly_explanation_payload: (m) => `SELECT build_anomaly_explanation_payload('${m}', '2024-01-15'::DATE, 14) AS payload;`,
  calculate_impact_from_json: () => `SELECT overall_impact, direct_impact, indirect_impact FROM calculate_impact_from_json('{"aggregation_method":"weighted_sum","scale_to":100,"parameters":[{"param_name":"criticality","param_value":85,"param_weight":0.5,"max_value":100,"impact_category":"direct"}]}'::JSONB);`,
  calculate_impact_batch: () => `SELECT asset_id, overall_impact, impact_level, rank_overall FROM calculate_impact_batch('[{"asset_id":"x","parameters":[...]}]'::JSONB) ORDER BY rank_overall;`,
  calculate_cascading_impact: () => `SELECT primary_impact, secondary_impact, blast_radius_score FROM calculate_cascading_impact(75.0, 25, 3, 0.50);`,
  classify_impact_level: () => `SELECT impact_level, recommended_action FROM classify_impact_level(72.4, 90, 70, 50, 30);`,
  calculate_vulnerability_likelihood: () => `SELECT likelihood_score, critical_vuln_contribution, high_vuln_contribution FROM calculate_vulnerability_likelihood('{"critical_vuln_count":4,"high_vuln_count":8}'::JSONB);`,
  calculate_time_weighted_likelihood: () => `SELECT likelihood_score, urgency_factor, dwell_time_penalty FROM calculate_time_weighted_likelihood('{"dwell_time_days":60,"days_until_due":3}'::JSONB);`,
  calculate_likelihood_trend: () => `SELECT trend_direction, forecast_30d FROM calculate_likelihood_trend('db-01', 90);`,
  calculate_sma: (t) => `WITH data AS (SELECT json_agg(json_build_object('time_period', d, 'value', v) ORDER BY d) AS arr FROM ${t || 'metrics_daily'} WHERE ...) SELECT * FROM data, calculate_sma(data.arr, 7);`,
  calculate_bollinger_bands: (t) => `WITH data AS (SELECT json_agg(...) AS arr FROM ${t || 'metrics_daily'}) SELECT * FROM calculate_bollinger_bands(data.arr, 14, 2);`,
  calculate_moving_correlation: () => `SELECT time_period, correlation, correlation_strength FROM calculate_moving_correlation(series_x.arr, series_y.arr, 14);`,
  calculate_autocorrelation: () => `SELECT lag_period, autocorrelation, is_significant FROM calculate_autocorrelation(data.arr, 14);`,
  test_stationarity: () => `SELECT test_name, is_stationary, recommendation FROM test_stationarity(data.arr);`,
  analyze_distribution: (t, d) => `SELECT group_name, mean_value, median_value, skewness FROM analyze_distribution(data.arr, '${d || 'group'}');`,
  calculate_statistical_trend: () => `SELECT trend_direction, slope, is_significant FROM calculate_statistical_trend(data.arr);`,
  forecast_linear: () => `SELECT forecast_period, forecast_value, lower_bound, upper_bound FROM forecast_linear(data.arr, 30);`,
  detect_anomalies: () => `SELECT time_period, original_value, anomaly_score, anomaly_type FROM detect_anomalies(data.arr, 14, 2.5) WHERE is_anomaly = true;`,
  detect_seasonality: () => `SELECT season_period, seasonal_index, above_average FROM detect_seasonality(data.arr, 'day_of_week');`,
  calculate_bootstrap_ci: () => `SELECT metric_type, point_estimate, ci_lower, ci_upper FROM calculate_bootstrap_ci(data.arr, 0.95, 1000);`,
  calculate_prepost_comparison: () => `SELECT entity_id, pre_value, post_value, percent_change, change_direction FROM calculate_prepost_comparison(data.arr, '2023-10-01'::TIMESTAMP);`,
  calculate_effect_sizes: () => `SELECT effect_size_type, effect_size_value, interpretation FROM calculate_effect_sizes(treatment.arr, control.arr);`,
  calculate_percent_change_comparison: () => `SELECT condition_value, percent_change, relative_uplift FROM calculate_percent_change_comparison(data.arr, 'condition', 'control');`,
};

function buildExample(template, idx) {
  const fn = template.fn;
  const sqlGen = SQL_TEMPLATES[fn];
  const sql = sqlGen ? sqlGen(template.metric, template.table, template.dim, template.sec_metric) : `SELECT * FROM ${fn}(...);`;

  return {
    id: `gen.${idx}`,
    function_name: fn,
    category: template.domain,
    question: template.q,
    description: `Domain-specific use of ${fn} for ${template.domain.toLowerCase()}. Uses ${template.table || 'metrics'} with metric '${template.metric}'.`,
    steps: [
      `Identify primary metric: ${template.metric}.`,
      `Prepare data from ${template.table || 'source table'}.`,
      `Call ${fn} with appropriate parameters.`,
      `Interpret results for ${template.domain} analytics.`
    ],
    sql,
    source_table: {
      table_name: template.table || 'metrics_daily',
      columns: [
        { name: 'metric_date', type: 'DATE', description: 'Example: 2024-01-15' },
        { name: template.metric, type: 'DECIMAL/INTEGER', description: 'Primary metric' },
        ...(template.dim ? [{ name: template.dim, type: 'TEXT', description: 'Grouping dimension' }] : [])
      ]
    },
    output_columns: [
      { name: 'metric_pair', sample_value: '—', description: 'Varies by function' },
      { name: 'correlation', sample_value: '—', description: 'Or metric-specific output' }
    ]
  };
}

// Generate all new examples
let genIdx = 1;
const newExamples = DOMAIN_TEMPLATES.map(t => {
  const ex = buildExample(t, genIdx++);
  // Refine output_columns based on function
  const outCols = {
    find_correlated_metrics: [{ name: 'metric_pair', sample_value: `${t.metric} ↔ other`, description: 'Correlated pair' }, { name: 'correlation', sample_value: '0.85', description: 'Pearson r' }],
    decompose_impact_by_dimension: [{ name: 'dimension_value', sample_value: t.dim || 'segment', description: 'Segment' }, { name: 'contribution_to_total', sample_value: '42%', description: 'Share of total' }],
    calculate_statistical_trend: [{ name: 'trend_direction', sample_value: 'DECREASING', description: 'Direction' }, { name: 'is_significant', sample_value: 'true', description: 'p < 0.05' }],
    detect_anomalies: [{ name: 'time_period', sample_value: '2024-01-15', description: 'Anomalous date' }, { name: 'anomaly_score', sample_value: '3.2', description: 'Z-score' }],
    calculate_bootstrap_ci: [{ name: 'point_estimate', sample_value: '8.4', description: 'Mean' }, { name: 'ci_lower', sample_value: '7.1', description: 'Lower bound' }],
  };
  ex.output_columns = outCols[t.fn] || ex.output_columns;
  return ex;
});

// Merge with base + newly generated
const merged = {
  ...existing,
  metadata: {
    ...existing.metadata,
    total_examples: baseExamples.length + newExamples.length,
    function_categories: 12
  },
  examples: [...baseExamples, ...newExamples]
};

const outPath = path.join(__dirname, 'sql_function_examples.json');
fs.writeFileSync(outPath, JSON.stringify(merged, null, 2), 'utf8');
console.log(`Generated ${newExamples.length} new examples. Total: ${merged.examples.length}`);
console.log(`Updated: ${outPath}`);
