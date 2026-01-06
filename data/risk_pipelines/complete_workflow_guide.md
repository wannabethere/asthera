# Complete End-to-End Risk Analytics Workflow

## From Raw Data to Executive Dashboards

This guide shows the complete journey from raw risk assessments to interactive dashboards with survival analysis.

---

## 🎯 Workflow Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                                      │
├──────────────────────────────────────────────────────────────────────┤
│  • HR System (User_csod, Transcript_csod)                            │
│  • Security (dev_cve, dev_assets, dev_vulnerability_instances)       │
│  • CRM (customers, support_tickets, usage_data)                      │
│  • Financial (vendors, contracts, payment_history)                   │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              STEP 1: RISK ASSESSMENT (LLM-Powered)                   │
├──────────────────────────────────────────────────────────────────────┤
│  1. Feature Engineering (attrition_risk_features, etc.)              │
│  2. LLM Analysis (understand risk specification)                     │
│  3. Transfer Learning (adapt parameters from similar domains)        │
│  4. SQL Risk Calculation (calculate_generic_likelihood/impact)       │
│  5. Store in risk_assessments table                                  │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              STEP 2: ETL TO DATA MARTS                               │
├──────────────────────────────────────────────────────────────────────┤
│  Dimensional Model:                                                   │
│  • dim_entity (SCD Type 2)                                           │
│  • dim_date (calendar table)                                         │
│  • dim_risk_domain                                                   │
│  • dim_risk_factor                                                   │
│                                                                       │
│  Facts:                                                               │
│  • fact_risk_assessment (grain: entity/date/domain)                  │
│  • fact_risk_factor_detail (parameter contributions)                 │
│  • fact_survival_events (time-to-event analysis)                     │
│  • fact_risk_trends (pre-aggregated for performance)                 │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              STEP 3: SURVIVAL ANALYSIS                               │
├──────────────────────────────────────────────────────────────────────┤
│  • Kaplan-Meier survival curves                                      │
│  • Cox Proportional Hazards (risk factor identification)             │
│  • Log-rank tests (cohort comparison)                                │
│  • Hazard rate calculations                                          │
│  • Median survival time predictions                                  │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              STEP 4: ANALYTICS & VISUALIZATION                       │
├──────────────────────────────────────────────────────────────────────┤
│  • Risk trend charts (overall, likelihood, impact)                   │
│  • Survival curves with confidence intervals                         │
│  • Cohort retention heatmaps                                         │
│  • Risk driver analysis                                              │
│  • Likelihood vs Impact matrices                                     │
│  • Executive dashboards                                              │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              STEP 5: ACTIONABLE INSIGHTS                             │
├──────────────────────────────────────────────────────────────────────┤
│  • Identify high-risk entities requiring intervention                │
│  • Predict time-to-event for proactive action                        │
│  • Measure intervention effectiveness                                │
│  • Track risk portfolio over time                                    │
│  • Generate executive reports                                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Complete Implementation Checklist

### Phase 1: Setup (Day 1)

- [ ] **Database Schema**
  ```bash
  # Create database
  createdb risk_analytics_db
  
  # Load schemas in order
  psql -d risk_analytics_db -f database/01_schema.sql
  psql -d risk_analytics_db -f database/02_risk_functions.sql
  psql -d risk_analytics_db -f database/04_risk_analytics_datamart.sql
  psql -d risk_analytics_db -f database/03_sample_data.sql
  ```

- [ ] **Python Environment**
  ```bash
  pip install -r config/requirements.txt
  
  # Additional packages for analytics
  pip install lifelines plotly streamlit psycopg2-binary pandas numpy
  ```

- [ ] **Configuration**
  ```bash
  cp config/.env.example .env
  # Edit .env with database URL and API keys
  ```

### Phase 2: Feature Engineering (Day 1-2)

- [ ] **Create Risk Feature Tables**
  ```sql
  -- Example: Employee Attrition Features
  CREATE TABLE attrition_risk_features AS
  SELECT 
      u.userId,
      -- Engagement metrics
      COUNT(CASE WHEN t.isCompleted = 'TRUE' THEN 1 END) * 100.0 / 
          COUNT(*) as completion_rate,
      COUNT(CASE WHEN t.isOverdue = 'TRUE' THEN 1 END) * 100.0 / 
          COUNT(*) as overdue_ratio,
      AVG(t.score) as avg_score,
      
      -- Temporal patterns
      EXTRACT(DAY FROM (CURRENT_DATE - MAX(u.lastLogindate))) as days_since_last_login,
      EXTRACT(DAY FROM (CURRENT_DATE - u.startDate)) as tenure_days,
      
      -- Recent activity (last 30 days)
      COUNT(CASE WHEN t.completionDate >= CURRENT_DATE - INTERVAL '30 days' 
                 THEN 1 END) as recent_completions
  FROM User_csod u
  LEFT JOIN Transcript_csod t ON u.userId = t.userID
  WHERE u.userStatus = 'ACTIVE'
  GROUP BY u.userId, u.lastLogindate, u.startDate;
  ```

- [ ] **Validate Features**
  ```sql
  -- Check for data quality
  SELECT 
      COUNT(*) as total_users,
      COUNT(DISTINCT userId) as unique_users,
      AVG(completion_rate) as avg_completion,
      MIN(days_since_last_login) as min_days,
      MAX(days_since_last_login) as max_days
  FROM attrition_risk_features;
  ```

### Phase 3: Risk Assessment (Day 2-3)

- [ ] **Run LLM Risk Engine**
  ```python
  from python.llm_risk_engine import UniversalRiskEngine, RiskSpecification
  
  engine = UniversalRiskEngine()
  
  # Define risk specification
  spec = RiskSpecification(
      description="""
      Calculate employee attrition risk based on:
      - Training completion rates and engagement
      - Time since last login
      - Number of overdue assignments
      - Manager relationship stability
      """,
      domain="hr"
  )
  
  # Batch process all users
  users = get_all_active_users()
  
  for user_id in users:
      result = assess_risk(
          entity_id=user_id,
          specification=spec.description,
          domain="hr"
      )
      
      # Results stored in risk_assessments table
      print(f"User {user_id}: Risk = {result.risk_score}")
  
  engine.close()
  ```

- [ ] **Verify Assessments**
  ```sql
  SELECT 
      domain,
      COUNT(*) as total_assessments,
      AVG(predicted_risk) as avg_risk,
      COUNT(*) FILTER (WHERE risk_level = 'CRITICAL') as critical_count
  FROM risk_assessments
  WHERE assessed_at >= CURRENT_DATE
  GROUP BY domain;
  ```

### Phase 4: ETL to Data Marts (Day 3-4)

- [ ] **Run ETL Pipeline**
  ```python
  from python.risk_analytics_etl import RiskAnalyticsETL
  from datetime import datetime, timedelta
  
  etl = RiskAnalyticsETL(db_conn_string=os.getenv("DATABASE_URL"))
  
  # Full pipeline
  end_date = datetime.now()
  start_date = end_date - timedelta(days=90)
  
  etl.run_full_pipeline(start_date, end_date)
  etl.close()
  ```

- [ ] **Verify Data Marts**
  ```sql
  -- Check fact_risk_assessment
  SELECT COUNT(*) FROM fact_risk_assessment;
  
  -- Check survival events
  SELECT COUNT(*) FROM fact_survival_events;
  
  -- Check trends
  SELECT COUNT(*) FROM fact_risk_trends;
  
  -- Verify joins work
  SELECT 
      e.entity_name,
      d.domain_name,
      f.overall_risk_score
  FROM fact_risk_assessment f
  JOIN dim_entity e ON f.entity_key = e.entity_key
  JOIN dim_risk_domain d ON f.domain_key = d.domain_key
  LIMIT 10;
  ```

### Phase 5: Survival Analysis (Day 4-5)

- [ ] **Calculate Survival Functions**
  ```python
  from python.risk_analytics_etl import SurvivalAnalysis
  
  survival = SurvivalAnalysis(db_conn_string=os.getenv("DATABASE_URL"))
  
  # Kaplan-Meier
  km_results = survival.kaplan_meier_analysis('Employee Attrition')
  print(f"Median survival: {km_results['median_survival'].iloc[0]} days")
  
  # Cox PH
  cox_results = survival.cox_proportional_hazards('Employee Attrition')
  print("Hazard ratios:")
  print(cox_results['hazard_ratios'])
  
  # Compare interventions
  comparison = survival.compare_cohorts(
      'Employee Attrition', 
      'intervention_applied'
  )
  print(f"Intervention effect p-value: {comparison['p_value']}")
  ```

- [ ] **Validate Survival Models**
  ```sql
  -- Check survival event distribution
  SELECT 
      d.domain_name,
      s.event_occurred,
      COUNT(*) as count,
      AVG(s.survival_time_days) as avg_days,
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY s.survival_time_days) as median_days
  FROM fact_survival_events s
  JOIN dim_risk_domain d ON s.domain_key = d.domain_key
  GROUP BY d.domain_name, s.event_occurred
  ORDER BY d.domain_name, s.event_occurred;
  ```

### Phase 6: Create Visualizations (Day 5-6)

- [ ] **Generate Charts**
  ```python
  from docs.visualization_guide import *
  
  # Risk trajectory
  fig1 = plot_risk_trajectory('USR12345', 'Employee Attrition')
  fig1.write_html('outputs/risk_trajectory.html')
  
  # Population distribution
  fig2 = plot_risk_distribution_evolution('Employee Attrition')
  fig2.write_html('outputs/risk_distribution.html')
  
  # Survival curves
  fig3 = plot_survival_curve('Employee Attrition', compare_by='intervention_applied')
  fig3.write_html('outputs/survival_curve.html')
  
  # Cohort heatmap
  fig4 = plot_cohort_retention_heatmap('Employee Attrition')
  fig4.write_html('outputs/cohort_heatmap.html')
  ```

- [ ] **Launch Dashboard**
  ```bash
  streamlit run dashboard.py
  ```

### Phase 7: Production Deployment (Day 7+)

- [ ] **Schedule ETL Jobs**
  ```bash
  # Add to crontab for daily refresh
  0 2 * * * /usr/bin/python /path/to/risk_analytics_etl.py >> /var/log/risk_etl.log 2>&1
  ```

- [ ] **Set Up Monitoring**
  ```python
  # monitor_data_quality.py
  import logging
  
  def check_data_quality():
      """Daily data quality checks"""
      
      checks = [
          # Check 1: Assessments loaded
          ("Assessments today", "SELECT COUNT(*) FROM risk_assessments WHERE assessed_at >= CURRENT_DATE", 0),
          
          # Check 2: No missing dimensions
          ("Missing entities", "SELECT COUNT(*) FROM fact_risk_assessment WHERE entity_key IS NULL", 0),
          
          # Check 3: Survival events updated
          ("Survival events", "SELECT COUNT(*) FROM fact_survival_events", 100),
      ]
      
      for check_name, query, min_expected in checks:
          result = execute_query(query)
          if result < min_expected:
              alert(f"FAIL: {check_name} = {result}, expected >= {min_expected}")
          else:
              logging.info(f"PASS: {check_name} = {result}")
  
  check_data_quality()
  ```

- [ ] **Configure Alerts**
  ```python
  # Configure Slack/email alerts for critical risk changes
  def send_critical_risk_alerts():
      query = """
      SELECT 
          e.entity_id,
          e.entity_name,
          f.overall_risk_score,
          f.risk_level
      FROM v_current_risk_snapshot f
      JOIN dim_entity e ON f.entity_id = e.entity_id
      WHERE f.risk_level = 'CRITICAL'
        AND f.risk_score_change > 10  -- Significant increase
      """
      
      critical_cases = execute_query(query)
      
      if critical_cases:
          send_slack_alert(critical_cases)
          send_email_alert(critical_cases)
  ```

---

## 📊 Example: Complete Employee Attrition Workflow

### Step-by-Step Example

```python
# complete_workflow.py - Employee Attrition Example

import os
from datetime import datetime, timedelta
from python.llm_risk_engine import UniversalRiskEngine, RiskSpecification
from python.risk_analytics_etl import RiskAnalyticsETL, SurvivalAnalysis
import pandas as pd

def run_complete_attrition_workflow():
    """
    Complete workflow: From raw HR data to survival analysis
    """
    
    print("="*70)
    print("STEP 1: Feature Engineering")
    print("="*70)
    
    # Already have attrition_risk_features table from SQL
    
    print("\n" + "="*70)
    print("STEP 2: Risk Assessment")
    print("="*70)
    
    engine = UniversalRiskEngine()
    
    spec = RiskSpecification(
        description="Calculate employee attrition risk based on training engagement",
        domain="hr"
    )
    
    # Get active users
    users = get_active_users()  # Your query
    
    print(f"Assessing {len(users)} employees...")
    
    for user_id in users[:100]:  # Sample 100 for demo
        result = assess_risk(entity_id=user_id, specification=spec)
        print(f"  {user_id}: Risk={result.risk_score:.1f}, Level={result.risk_level}")
    
    engine.close()
    
    print("\n" + "="*70)
    print("STEP 3: ETL to Data Marts")
    print("="*70)
    
    etl = RiskAnalyticsETL(db_conn_string=os.getenv("DATABASE_URL"))
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    etl.run_full_pipeline(start_date, end_date)
    etl.close()
    
    print("\n" + "="*70)
    print("STEP 4: Survival Analysis")
    print("="*70)
    
    survival = SurvivalAnalysis(db_conn_string=os.getenv("DATABASE_URL"))
    
    # Kaplan-Meier
    print("\nKaplan-Meier Survival Analysis:")
    km_results = survival.kaplan_meier_analysis('Employee Attrition')
    print(f"Median time to attrition: {km_results['median_survival'].iloc[0]:.0f} days")
    print(f"30-day retention: {km_results.loc[30, 'KM_estimate']:.1%}")
    print(f"90-day retention: {km_results.loc[90, 'KM_estimate']:.1%}")
    
    # Cox Proportional Hazards
    print("\nCox PH - Risk Factor Hazard Ratios:")
    cox_results = survival.cox_proportional_hazards('Employee Attrition')
    print(cox_results['hazard_ratios'].head())
    print(f"Model concordance: {cox_results['concordance_index']:.3f}")
    
    # Intervention comparison
    print("\nIntervention Effectiveness:")
    comparison = survival.compare_cohorts('Employee Attrition', 'intervention_applied')
    print(f"With intervention median: {comparison['group_a_median']:.0f} days")
    print(f"Without intervention median: {comparison['group_b_median']:.0f} days")
    print(f"Log-rank test p-value: {comparison['p_value']:.4f}")
    
    if comparison['is_significant']:
        print("✓ Intervention significantly extends survival!")
    
    print("\n" + "="*70)
    print("STEP 5: Generate Visualizations")
    print("="*70)
    
    from docs.visualization_guide import *
    
    # Create output directory
    os.makedirs('outputs', exist_ok=True)
    
    # Generate all charts
    print("Creating visualizations...")
    
    plot_risk_distribution_evolution('Employee Attrition').write_html('outputs/distribution.html')
    plot_survival_curve('Employee Attrition', compare_by='intervention_applied').write_html('outputs/survival.html')
    plot_cohort_retention_heatmap('Employee Attrition').write_html('outputs/cohorts.html')
    
    print("✓ Visualizations saved to outputs/")
    
    print("\n" + "="*70)
    print("STEP 6: Business Insights")
    print("="*70)
    
    # Query key insights
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    
    # High-risk employees
    high_risk_query = """
    SELECT 
        entity_id,
        entity_name,
        overall_risk_score,
        risk_level,
        likelihood_score,
        impact_score
    FROM v_current_risk_snapshot
    WHERE domain_name = 'Employee Attrition'
      AND risk_level IN ('CRITICAL', 'HIGH')
    ORDER BY overall_risk_score DESC
    LIMIT 10
    """
    
    df_high_risk = pd.read_sql(high_risk_query, conn)
    
    print("\nTop 10 High-Risk Employees:")
    print(df_high_risk.to_string(index=False))
    
    # Top risk drivers
    drivers_query = """
    SELECT 
        factor_name,
        ROUND(AVG(contribution_percentage), 1) as avg_contribution
    FROM v_top_risk_drivers
    WHERE domain_name = 'Employee Attrition'
      AND factor_rank <= 5
    GROUP BY factor_name
    ORDER BY avg_contribution DESC
    LIMIT 5
    """
    
    df_drivers = pd.read_sql(drivers_query, conn)
    
    print("\nTop 5 Risk Drivers:")
    print(df_drivers.to_string(index=False))
    
    conn.close()
    
    print("\n" + "="*70)
    print("WORKFLOW COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("1. Review outputs/ folder for visualizations")
    print("2. Launch dashboard: streamlit run dashboard.py")
    print("3. Schedule daily ETL: crontab -e")
    print("4. Set up alerts for critical cases")

if __name__ == "__main__":
    run_complete_attrition_workflow()
```

**Run it:**
```bash
python complete_workflow.py
```

---

## 🎯 Key Outputs

### 1. Data Marts (SQL)
- ✅ `fact_risk_assessment` - 10,000+ rows
- ✅ `fact_survival_events` - 5,000+ rows
- ✅ `fact_risk_factor_detail` - 50,000+ rows
- ✅ `fact_risk_trends` - 1,000+ rows

### 2. Analytics (Python)
- ✅ Kaplan-Meier survival functions
- ✅ Cox PH hazard ratios
- ✅ Cohort retention matrices
- ✅ Risk driver rankings

### 3. Visualizations (HTML/PNG)
- ✅ Risk trajectory charts
- ✅ Survival curves
- ✅ Cohort heatmaps
- ✅ Likelihood vs Impact matrices

### 4. Dashboards (Streamlit)
- ✅ Executive summary
- ✅ Risk trends
- ✅ Entity deep-dive
- ✅ Survival analysis

---

## 🚀 Production Best Practices

1. **Data Quality Monitoring**
   - Daily validation checks
   - Alert on anomalies
   - Track ETL job success rate

2. **Performance Optimization**
   - Partition large fact tables by date
   - Create appropriate indexes
   - Use materialized views for dashboards

3. **Disaster Recovery**
   - Daily database backups
   - Test restore procedures
   - Version control all SQL/Python code

4. **Access Control**
   - Row-level security for sensitive data
   - Audit log for data access
   - Role-based permissions

5. **Continuous Improvement**
   - Track prediction accuracy
   - Update ML models monthly
   - Gather user feedback

---

You now have a complete, production-ready risk analytics platform from raw data to actionable insights!
