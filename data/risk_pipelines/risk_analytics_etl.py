"""
Risk Analytics Data Mart - ETL Pipeline
Transforms raw risk assessments into dimensional models with survival analysis
"""

import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import logrank_test

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class RiskAssessmentRecord:
    """Raw risk assessment from source system"""
    entity_id: str
    domain: str
    assessment_date: datetime
    risk_score: float
    likelihood_score: float
    impact_score: float
    risk_level: str
    transfer_confidence: float
    likelihood_parameters: Dict
    impact_parameters: Dict


@dataclass
class SurvivalRecord:
    """Survival analysis record"""
    entity_id: str
    domain: str
    entry_date: datetime
    exit_date: Optional[datetime]
    event_occurred: bool
    survival_days: int
    risk_scores: List[float]


# ============================================================================
# ETL PIPELINE CLASS
# ============================================================================

class RiskAnalyticsETL:
    """
    ETL pipeline for risk analytics data marts
    Handles dimension loading, fact loading, and survival analysis
    """
    
    def __init__(self, db_conn_string: str):
        self.conn_string = db_conn_string
        self.conn = psycopg2.connect(db_conn_string)
        self.conn.autocommit = False
        
    def run_full_pipeline(self, start_date: datetime, end_date: datetime):
        """
        Execute complete ETL pipeline
        
        Steps:
        1. Load dimensions (entities, factors)
        2. Load fact_risk_assessment
        3. Load fact_risk_factor_detail
        4. Build survival events
        5. Calculate trends
        6. Refresh analytics views
        """
        try:
            logger.info(f"Starting ETL pipeline for {start_date} to {end_date}")
            
            # Step 1: Load dimensions
            logger.info("Step 1: Loading dimensions...")
            self.load_entity_dimension()
            self.load_risk_factor_dimension()
            
            # Step 2: Load fact tables
            logger.info("Step 2: Loading fact_risk_assessment...")
            assessment_keys = self.load_risk_assessments(start_date, end_date)
            
            logger.info("Step 3: Loading fact_risk_factor_detail...")
            self.load_risk_factor_details(assessment_keys)
            
            # Step 4: Survival analysis
            logger.info("Step 4: Building survival events...")
            self.build_survival_events()
            
            # Step 5: Calculate trends
            logger.info("Step 5: Calculating risk trends...")
            self.calculate_risk_trends()
            
            # Step 6: Refresh analytics
            logger.info("Step 6: Refreshing analytics views...")
            self.refresh_analytics_views()
            
            self.conn.commit()
            logger.info("ETL pipeline completed successfully")
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"ETL pipeline failed: {e}")
            raise
    
    
    # ========================================================================
    # DIMENSION LOADING
    # ========================================================================
    
    def load_entity_dimension(self):
        """
        Load entity dimension with SCD Type 2 logic
        """
        cursor = self.conn.cursor()
        
        # Get entities from source system (your User_csod, dev_assets, etc.)
        query = """
        -- Example: Load from multiple source tables
        WITH source_entities AS (
            -- HR entities
            SELECT DISTINCT
                userId as entity_id,
                fullName as entity_name,
                'employee' as entity_type,
                division as level_1,
                department as level_2,
                team as level_3,
                NULL as level_4,
                position_criticality as business_criticality,
                'hr' as risk_classification,
                region,
                country,
                state as state_province,
                city,
                NOW() as effective_start_date
            FROM User_csod
            WHERE userStatus = 'ACTIVE'
            
            UNION ALL
            
            -- Security entities (assets)
            SELECT DISTINCT
                assetId as entity_id,
                assetName as entity_name,
                'it_asset' as entity_type,
                business_unit as level_1,
                asset_type as level_2,
                location as level_3,
                NULL as level_4,
                asset_criticality as business_criticality,
                'security' as risk_classification,
                region,
                country,
                NULL as state_province,
                datacenter as city,
                NOW() as effective_start_date
            FROM dev_assets
            WHERE is_active = TRUE
            
            -- Add more entity sources...
        ),
        
        -- Detect changes (SCD Type 2)
        changed_entities AS (
            SELECT 
                s.*,
                d.entity_key,
                d.is_current
            FROM source_entities s
            LEFT JOIN dim_entity d ON s.entity_id = d.entity_id AND d.is_current = TRUE
            WHERE d.entity_key IS NULL  -- New entity
               OR (d.entity_name != s.entity_name  -- Attribute changed
                   OR d.level_1 != s.level_1
                   OR d.business_criticality != s.business_criticality)
        )
        
        -- Close out old records
        UPDATE dim_entity d
        SET 
            effective_end_date = CURRENT_DATE - INTERVAL '1 day',
            is_current = FALSE,
            updated_at = NOW()
        FROM changed_entities c
        WHERE d.entity_id = c.entity_id 
          AND d.is_current = TRUE
          AND c.entity_key IS NOT NULL;  -- Only for changed, not new
        
        -- Insert new records
        INSERT INTO dim_entity (
            entity_id, entity_name, entity_type, 
            level_1, level_2, level_3, level_4,
            business_criticality, risk_classification,
            region, country, state_province, city,
            effective_start_date, effective_end_date, is_current
        )
        SELECT 
            entity_id, entity_name, entity_type,
            level_1, level_2, level_3, level_4,
            business_criticality, risk_classification,
            region, country, state_province, city,
            CURRENT_DATE, NULL, TRUE
        FROM changed_entities
        ON CONFLICT (entity_id, effective_start_date) DO NOTHING;
        """
        
        cursor.execute(query)
        rows_affected = cursor.rowcount
        logger.info(f"Loaded {rows_affected} entity dimension records")
    
    
    def load_risk_factor_dimension(self):
        """
        Load risk factors from parameter configurations
        """
        cursor = self.conn.cursor()
        
        # Extract unique factors from ml_learned_parameters
        query = """
        WITH factor_configs AS (
            SELECT DISTINCT
                jsonb_array_elements(config->'weights')->>'parameter' as factor_code,
                domain
            FROM ml_learned_parameters
            WHERE is_active = TRUE
        )
        INSERT INTO dim_risk_factor (
            factor_code,
            factor_name,
            factor_category,
            description,
            is_active
        )
        SELECT 
            factor_code,
            INITCAP(REPLACE(factor_code, '_', ' ')) as factor_name,
            CASE 
                WHEN factor_code LIKE '%_rate' THEN 'likelihood'
                WHEN factor_code LIKE '%_impact' THEN 'impact'
                WHEN factor_code LIKE '%_days' THEN 'temporal'
                ELSE 'other'
            END as factor_category,
            'Auto-generated from configuration' as description,
            TRUE as is_active
        FROM factor_configs
        ON CONFLICT (factor_code) DO UPDATE
        SET is_active = TRUE;
        """
        
        cursor.execute(query)
        logger.info(f"Loaded {cursor.rowcount} risk factor records")
    
    
    # ========================================================================
    # FACT TABLE LOADING
    # ========================================================================
    
    def load_risk_assessments(self, start_date: datetime, end_date: datetime) -> List[int]:
        """
        Load fact_risk_assessment from source risk_assessments table
        Returns list of assessment keys for downstream processing
        """
        cursor = self.conn.cursor()
        
        query = """
        WITH source_assessments AS (
            SELECT 
                ra.id as assessment_id,
                ra.entity_id,
                ra.domain,
                ra.assessed_at,
                ra.predicted_risk as overall_risk_score,
                ra.predicted_likelihood as likelihood_score,
                ra.predicted_impact as impact_score,
                ra.risk_level,
                ra.transfer_confidence,
                ra.likelihood_parameters,
                ra.impact_parameters,
                
                -- Calculate changes from previous assessment
                LAG(ra.predicted_risk) OVER (
                    PARTITION BY ra.entity_id, ra.domain 
                    ORDER BY ra.assessed_at
                ) as prev_risk_score,
                
                -- Days since last assessment
                EXTRACT(DAY FROM (
                    ra.assessed_at - LAG(ra.assessed_at) OVER (
                        PARTITION BY ra.entity_id, ra.domain 
                        ORDER BY ra.assessed_at
                    )
                ))::INTEGER as days_since_last
                
            FROM risk_assessments ra
            WHERE ra.assessed_at >= %s
              AND ra.assessed_at < %s
        )
        INSERT INTO fact_risk_assessment (
            entity_key,
            assessment_date_key,
            domain_key,
            overall_risk_score,
            likelihood_score,
            impact_score,
            risk_level,
            risk_level_numeric,
            transfer_confidence,
            risk_score_change,
            risk_level_change,
            days_since_last_assessment,
            days_since_first_at_risk,
            is_censored,
            assessment_id,
            assessed_at
        )
        SELECT 
            e.entity_key,
            TO_CHAR(s.assessed_at::DATE, 'YYYYMMDD')::INTEGER as assessment_date_key,
            d.domain_key,
            s.overall_risk_score,
            s.likelihood_score,
            s.impact_score,
            s.risk_level,
            CASE s.risk_level
                WHEN 'CRITICAL' THEN 5
                WHEN 'HIGH' THEN 4
                WHEN 'MEDIUM' THEN 3
                WHEN 'LOW' THEN 2
                ELSE 1
            END as risk_level_numeric,
            s.transfer_confidence,
            s.overall_risk_score - s.prev_risk_score as risk_score_change,
            CASE 
                WHEN s.overall_risk_score - s.prev_risk_score > 5 THEN 'INCREASED'
                WHEN s.overall_risk_score - s.prev_risk_score < -5 THEN 'DECREASED'
                ELSE 'STABLE'
            END as risk_level_change,
            s.days_since_last,
            
            -- Days since first at-risk (risk_score >= 50)
            EXTRACT(DAY FROM (
                s.assessed_at - (
                    SELECT MIN(ra2.assessed_at) 
                    FROM risk_assessments ra2 
                    WHERE ra2.entity_id = s.entity_id 
                      AND ra2.domain = s.domain
                      AND ra2.predicted_risk >= 50
                )
            ))::INTEGER as days_since_first_at_risk,
            
            -- Censored if no event occurred yet
            NOT EXISTS (
                SELECT 1 FROM risk_outcomes ro 
                WHERE ro.entity_id = s.entity_id 
                  AND ro.domain = s.domain
                  AND ro.actual_outcome = TRUE
            ) as is_censored,
            
            s.assessment_id,
            s.assessed_at
        FROM source_assessments s
        JOIN dim_entity e ON s.entity_id = e.entity_id AND e.is_current = TRUE
        JOIN dim_risk_domain d ON s.domain = d.domain_code
        RETURNING assessment_key;
        """
        
        cursor.execute(query, (start_date, end_date))
        assessment_keys = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Loaded {len(assessment_keys)} risk assessment records")
        return assessment_keys
    
    
    def load_risk_factor_details(self, assessment_keys: List[int]):
        """
        Load detailed risk factor contributions
        """
        if not assessment_keys:
            return
        
        cursor = self.conn.cursor()
        
        # Process in batches
        batch_size = 1000
        for i in range(0, len(assessment_keys), batch_size):
            batch = assessment_keys[i:i+batch_size]
            
            query = """
            WITH assessment_params AS (
                SELECT 
                    fa.assessment_key,
                    fa.assessment_id,
                    
                    -- Expand likelihood parameters
                    jsonb_array_elements(ra.likelihood_parameters) as likelihood_param,
                    
                    -- Expand impact parameters  
                    jsonb_array_elements(ra.impact_parameters) as impact_param
                    
                FROM fact_risk_assessment fa
                JOIN risk_assessments ra ON fa.assessment_id = ra.id::TEXT
                WHERE fa.assessment_key = ANY(%s)
            ),
            
            all_factors AS (
                -- Likelihood factors
                SELECT 
                    assessment_key,
                    likelihood_param->>'param_name' as factor_code,
                    'likelihood' as factor_category,
                    (likelihood_param->>'param_value')::DECIMAL as raw_value,
                    (likelihood_param->>'normalized_value')::DECIMAL as normalized_value,
                    (likelihood_param->>'decayed_value')::DECIMAL as decayed_value,
                    (likelihood_param->>'weighted_score')::DECIMAL as weighted_score,
                    (likelihood_param->>'param_weight')::DECIMAL as weight_applied,
                    likelihood_param->>'decay_function' as decay_function,
                    (likelihood_param->>'decay_rate')::DECIMAL as decay_rate,
                    (likelihood_param->>'time_delta')::DECIMAL as time_delta
                FROM assessment_params
                
                UNION ALL
                
                -- Impact factors
                SELECT 
                    assessment_key,
                    impact_param->>'param_name' as factor_code,
                    'impact' as factor_category,
                    (impact_param->>'param_value')::DECIMAL as raw_value,
                    (impact_param->>'normalized_value')::DECIMAL as normalized_value,
                    NULL as decayed_value,
                    (impact_param->>'weighted_score')::DECIMAL as weighted_score,
                    (impact_param->>'param_weight')::DECIMAL as weight_applied,
                    NULL as decay_function,
                    NULL as decay_rate,
                    NULL as time_delta
                FROM assessment_params
            ),
            
            -- Calculate contribution percentages
            factors_with_contribution AS (
                SELECT 
                    af.*,
                    100.0 * af.weighted_score / SUM(af.weighted_score) OVER (
                        PARTITION BY af.assessment_key
                    ) as contribution_percentage,
                    ROW_NUMBER() OVER (
                        PARTITION BY af.assessment_key 
                        ORDER BY af.weighted_score DESC
                    ) <= 3 as is_primary_driver
                FROM all_factors af
            )
            
            INSERT INTO fact_risk_factor_detail (
                assessment_key,
                factor_key,
                raw_value,
                normalized_value,
                decayed_value,
                weighted_score,
                weight_applied,
                decay_function,
                decay_rate,
                time_delta,
                contribution_percentage,
                is_primary_driver
            )
            SELECT 
                f.assessment_key,
                rf.factor_key,
                f.raw_value,
                f.normalized_value,
                f.decayed_value,
                f.weighted_score,
                f.weight_applied,
                f.decay_function,
                f.decay_rate,
                f.time_delta,
                f.contribution_percentage,
                f.is_primary_driver
            FROM factors_with_contribution f
            JOIN dim_risk_factor rf ON f.factor_code = rf.factor_code;
            """
            
            cursor.execute(query, (batch,))
            logger.info(f"Loaded factor details for batch {i//batch_size + 1}")
    
    
    # ========================================================================
    # SURVIVAL ANALYSIS
    # ========================================================================
    
    def build_survival_events(self):
        """
        Build survival events from risk assessments and outcomes
        
        Key concepts:
        - Entry date: When entity first entered high-risk state (risk >= 50)
        - Exit date: When event occurred OR censoring date
        - Event: Attrition, exploitation, churn, etc.
        - Censoring: Entity still at risk but event hasn't occurred yet
        """
        cursor = self.conn.cursor()
        
        query = """
        WITH risk_cohorts AS (
            -- Identify when each entity entered at-risk state
            SELECT DISTINCT ON (ra.entity_id, ra.domain)
                ra.entity_id,
                ra.domain,
                ra.assessed_at as entry_date,
                ra.predicted_risk as entry_risk_score
            FROM risk_assessments ra
            WHERE ra.predicted_risk >= 50  -- High risk threshold
            ORDER BY ra.entity_id, ra.domain, ra.assessed_at ASC
        ),
        
        outcomes AS (
            -- Get actual outcomes (events)
            SELECT 
                ro.entity_id,
                ro.domain,
                ro.outcome_date as exit_date,
                ro.actual_outcome as event_occurred,
                ro.outcome_severity
            FROM risk_outcomes ro
        ),
        
        survival_calculations AS (
            SELECT 
                rc.entity_id,
                rc.domain,
                rc.entry_date,
                
                -- Exit date: outcome date if event occurred, else censoring date
                COALESCE(o.exit_date, CURRENT_DATE) as exit_date,
                
                -- Event indicator
                COALESCE(o.event_occurred, FALSE) as event_occurred,
                
                -- Survival time in days
                EXTRACT(DAY FROM (
                    COALESCE(o.exit_date, CURRENT_DATE) - rc.entry_date
                ))::INTEGER as survival_time_days,
                
                -- Risk scores at key timepoints
                rc.entry_risk_score,
                
                (SELECT ra.predicted_risk 
                 FROM risk_assessments ra 
                 WHERE ra.entity_id = rc.entity_id 
                   AND ra.domain = rc.domain
                   AND ra.assessed_at >= rc.entry_date + INTERVAL '30 days'
                 ORDER BY ra.assessed_at LIMIT 1
                ) as risk_score_30d,
                
                (SELECT ra.predicted_risk 
                 FROM risk_assessments ra 
                 WHERE ra.entity_id = rc.entity_id 
                   AND ra.domain = rc.domain
                   AND ra.assessed_at >= rc.entry_date + INTERVAL '60 days'
                 ORDER BY ra.assessed_at LIMIT 1
                ) as risk_score_60d,
                
                (SELECT ra.predicted_risk 
                 FROM risk_assessments ra 
                 WHERE ra.entity_id = rc.entity_id 
                   AND ra.domain = rc.domain
                   AND ra.assessed_at >= rc.entry_date + INTERVAL '90 days'
                 ORDER BY ra.assessed_at LIMIT 1
                ) as risk_score_90d,
                
                COALESCE(o.outcome_severity, 0) as risk_score_at_event,
                
                -- Trend analysis
                CASE 
                    WHEN (
                        SELECT CORR(
                            EXTRACT(DAY FROM ra.assessed_at - rc.entry_date),
                            ra.predicted_risk
                        )
                        FROM risk_assessments ra
                        WHERE ra.entity_id = rc.entity_id 
                          AND ra.domain = rc.domain
                          AND ra.assessed_at >= rc.entry_date
                    ) > 0.3 THEN 'INCREASING'
                    WHEN (
                        SELECT CORR(
                            EXTRACT(DAY FROM ra.assessed_at - rc.entry_date),
                            ra.predicted_risk
                        )
                        FROM risk_assessments ra
                        WHERE ra.entity_id = rc.entity_id 
                          AND ra.domain = rc.domain
                          AND ra.assessed_at >= rc.entry_date
                    ) < -0.3 THEN 'DECREASING'
                    ELSE 'STABLE'
                END as risk_trend,
                
                -- Peak risk
                (SELECT MAX(ra.predicted_risk) 
                 FROM risk_assessments ra 
                 WHERE ra.entity_id = rc.entity_id 
                   AND ra.domain = rc.domain
                   AND ra.assessed_at >= rc.entry_date
                ) as peak_risk_score,
                
                -- Cohort grouping
                DATE_TRUNC('month', rc.entry_date)::DATE as cohort_month,
                DATE_TRUNC('quarter', rc.entry_date)::DATE as cohort_quarter,
                EXTRACT(YEAR FROM rc.entry_date)::INTEGER as cohort_year
                
            FROM risk_cohorts rc
            LEFT JOIN outcomes o ON rc.entity_id = o.entity_id 
                                 AND rc.domain = o.domain
        )
        
        INSERT INTO fact_survival_events (
            entity_key,
            event_date_key,
            domain_key,
            event_type,
            event_occurred,
            entry_date,
            exit_date,
            survival_time_days,
            risk_score_at_entry,
            risk_score_at_30_days,
            risk_score_at_60_days,
            risk_score_at_90_days,
            risk_score_at_event,
            risk_trend,
            peak_risk_score,
            cohort_month,
            cohort_quarter,
            cohort_fiscal_year
        )
        SELECT 
            e.entity_key,
            TO_CHAR(sc.exit_date, 'YYYYMMDD')::INTEGER as event_date_key,
            d.domain_key,
            d.domain_code as event_type,
            sc.event_occurred,
            sc.entry_date,
            sc.exit_date,
            sc.survival_time_days,
            sc.entry_risk_score,
            sc.risk_score_30d,
            sc.risk_score_60d,
            sc.risk_score_90d,
            sc.risk_score_at_event,
            sc.risk_trend,
            sc.peak_risk_score,
            sc.cohort_month,
            sc.cohort_quarter,
            EXTRACT(YEAR FROM sc.cohort_month)::INTEGER
        FROM survival_calculations sc
        JOIN dim_entity e ON sc.entity_id = e.entity_id AND e.is_current = TRUE
        JOIN dim_risk_domain d ON sc.domain = d.domain_code
        ON CONFLICT DO NOTHING;
        """
        
        cursor.execute(query)
        logger.info(f"Built {cursor.rowcount} survival event records")
    
    
    def calculate_risk_trends(self):
        """
        Calculate aggregated risk trends
        Pre-compute for dashboard performance
        """
        cursor = self.conn.cursor()
        
        # Daily trends
        query_daily = """
        INSERT INTO fact_risk_trends (
            domain_key,
            snapshot_date_key,
            aggregation_level,
            entity_type,
            total_entities,
            total_assessments,
            avg_risk_score,
            median_risk_score,
            stddev_risk_score,
            min_risk_score,
            max_risk_score,
            p95_risk_score,
            count_critical,
            count_high,
            count_medium,
            count_low,
            avg_risk_change,
            entities_increased,
            entities_decreased,
            entities_stable
        )
        SELECT 
            f.domain_key,
            f.assessment_date_key,
            'daily' as aggregation_level,
            e.entity_type,
            COUNT(DISTINCT f.entity_key) as total_entities,
            COUNT(*) as total_assessments,
            AVG(f.overall_risk_score) as avg_risk_score,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.overall_risk_score) as median_risk_score,
            STDDEV(f.overall_risk_score) as stddev_risk_score,
            MIN(f.overall_risk_score) as min_risk_score,
            MAX(f.overall_risk_score) as max_risk_score,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY f.overall_risk_score) as p95_risk_score,
            COUNT(*) FILTER (WHERE f.risk_level = 'CRITICAL') as count_critical,
            COUNT(*) FILTER (WHERE f.risk_level = 'HIGH') as count_high,
            COUNT(*) FILTER (WHERE f.risk_level = 'MEDIUM') as count_medium,
            COUNT(*) FILTER (WHERE f.risk_level = 'LOW') as count_low,
            AVG(f.risk_score_change) as avg_risk_change,
            COUNT(*) FILTER (WHERE f.risk_level_change = 'INCREASED') as entities_increased,
            COUNT(*) FILTER (WHERE f.risk_level_change = 'DECREASED') as entities_decreased,
            COUNT(*) FILTER (WHERE f.risk_level_change = 'STABLE') as entities_stable
        FROM fact_risk_assessment f
        JOIN dim_entity e ON f.entity_key = e.entity_key
        WHERE f.assessment_date_key >= TO_CHAR(CURRENT_DATE - INTERVAL '90 days', 'YYYYMMDD')::INTEGER
        GROUP BY f.domain_key, f.assessment_date_key, e.entity_type
        ON CONFLICT (domain_key, snapshot_date_key, aggregation_level, entity_type, level_1, risk_level)
        DO UPDATE SET
            total_entities = EXCLUDED.total_entities,
            avg_risk_score = EXCLUDED.avg_risk_score,
            median_risk_score = EXCLUDED.median_risk_score;
        """
        
        cursor.execute(query_daily)
        logger.info(f"Calculated {cursor.rowcount} daily trend records")
        
        # Weekly trends
        query_weekly = """
        INSERT INTO fact_risk_trends (
            domain_key,
            snapshot_date_key,
            aggregation_level,
            entity_type,
            total_entities,
            avg_risk_score,
            median_risk_score,
            count_critical,
            count_high,
            count_medium,
            count_low
        )
        SELECT 
            f.domain_key,
            dt.iso_week as snapshot_date_key,
            'weekly' as aggregation_level,
            e.entity_type,
            COUNT(DISTINCT f.entity_key) as total_entities,
            AVG(f.overall_risk_score) as avg_risk_score,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.overall_risk_score) as median_risk_score,
            COUNT(*) FILTER (WHERE f.risk_level = 'CRITICAL') as count_critical,
            COUNT(*) FILTER (WHERE f.risk_level = 'HIGH') as count_high,
            COUNT(*) FILTER (WHERE f.risk_level = 'MEDIUM') as count_medium,
            COUNT(*) FILTER (WHERE f.risk_level = 'LOW') as count_low
        FROM fact_risk_assessment f
        JOIN dim_entity e ON f.entity_key = e.entity_key
        JOIN dim_date dt ON f.assessment_date_key = dt.date_key
        WHERE dt.date_actual >= CURRENT_DATE - INTERVAL '26 weeks'
        GROUP BY f.domain_key, dt.iso_week, e.entity_type
        ON CONFLICT (domain_key, snapshot_date_key, aggregation_level, entity_type, level_1, risk_level)
        DO UPDATE SET
            total_entities = EXCLUDED.total_entities,
            avg_risk_score = EXCLUDED.avg_risk_score;
        """
        
        cursor.execute(query_weekly)
        logger.info(f"Calculated {cursor.rowcount} weekly trend records")
    
    
    def refresh_analytics_views(self):
        """
        Refresh materialized views for analytics
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT refresh_risk_analytics_marts();")
        logger.info("Refreshed analytics views")
    
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# ============================================================================
# SURVIVAL ANALYSIS FUNCTIONS
# ============================================================================

class SurvivalAnalysis:
    """
    Survival analysis calculations using lifelines library
    Kaplan-Meier, Cox Proportional Hazards, Log-rank tests
    """
    
    def __init__(self, db_conn_string: str):
        self.conn_string = db_conn_string
        
    def kaplan_meier_analysis(self, domain: str, cohort_month: str = None) -> pd.DataFrame:
        """
        Kaplan-Meier survival analysis
        
        Returns survival probability over time
        """
        conn = psycopg2.connect(self.conn_string)
        
        # Load survival data
        query = """
        SELECT 
            survival_time_days,
            event_occurred::INTEGER as event
        FROM fact_survival_events s
        JOIN dim_risk_domain d ON s.domain_key = d.domain_key
        WHERE d.domain_name = %s
        """
        
        params = [domain]
        if cohort_month:
            query += " AND s.cohort_month = %s"
            params.append(cohort_month)
        
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        # Fit Kaplan-Meier
        kmf = KaplanMeierFitter()
        kmf.fit(
            durations=df['survival_time_days'],
            event_observed=df['event']
        )
        
        # Get survival function
        survival_function = kmf.survival_function_
        survival_function['median_survival'] = kmf.median_survival_time_
        survival_function['confidence_interval_lower'] = kmf.confidence_interval_survival_function_.iloc[:, 0]
        survival_function['confidence_interval_upper'] = kmf.confidence_interval_survival_function_.iloc[:, 1]
        
        logger.info(f"Kaplan-Meier analysis completed for {domain}")
        logger.info(f"Median survival time: {kmf.median_survival_time_:.1f} days")
        
        return survival_function
    
    
    def cox_proportional_hazards(self, domain: str) -> Dict:
        """
        Cox Proportional Hazards regression
        
        Identifies which risk factors predict time-to-event
        """
        conn = psycopg2.connect(self.conn_string)
        
        # Load survival data with covariates
        query = """
        SELECT 
            s.survival_time_days,
            s.event_occurred::INTEGER as event,
            s.risk_score_at_entry,
            s.risk_score_at_30_days,
            s.risk_trend,
            s.intervention_applied::INTEGER as intervention,
            e.entity_type,
            e.business_criticality
        FROM fact_survival_events s
        JOIN dim_risk_domain d ON s.domain_key = d.domain_key
        JOIN dim_entity e ON s.entity_key = e.entity_key
        WHERE d.domain_name = %s
          AND s.risk_score_at_entry IS NOT NULL
        """
        
        df = pd.read_sql(query, conn, params=[domain])
        conn.close()
        
        # One-hot encode categorical variables
        df_encoded = pd.get_dummies(df, columns=['risk_trend', 'entity_type', 'business_criticality'])
        
        # Fit Cox model
        cph = CoxPHFitter()
        cph.fit(
            df_encoded,
            duration_col='survival_time_days',
            event_col='event'
        )
        
        # Extract results
        results = {
            'summary': cph.summary,
            'concordance_index': cph.concordance_index_,
            'hazard_ratios': np.exp(cph.params_),
            'log_likelihood': cph.log_likelihood_
        }
        
        logger.info(f"Cox PH analysis completed for {domain}")
        logger.info(f"Concordance index: {cph.concordance_index_:.3f}")
        
        return results
    
    
    def compare_cohorts(self, domain: str, comparison_field: str) -> Dict:
        """
        Compare survival curves between groups using log-rank test
        
        Example: Compare employees who received intervention vs those who didn't
        """
        conn = psycopg2.connect(self.conn_string)
        
        query = f"""
        SELECT 
            s.survival_time_days,
            s.event_occurred::INTEGER as event,
            s.{comparison_field} as group_label
        FROM fact_survival_events s
        JOIN dim_risk_domain d ON s.domain_key = d.domain_key
        WHERE d.domain_name = %s
          AND s.{comparison_field} IS NOT NULL
        """
        
        df = pd.read_sql(query, conn, params=[domain])
        conn.close()
        
        # Get unique groups
        groups = df['group_label'].unique()
        
        if len(groups) != 2:
            raise ValueError(f"Expected 2 groups, found {len(groups)}")
        
        # Split into two groups
        group_a = df[df['group_label'] == groups[0]]
        group_b = df[df['group_label'] == groups[1]]
        
        # Perform log-rank test
        results = logrank_test(
            group_a['survival_time_days'],
            group_b['survival_time_days'],
            event_observed_A=group_a['event'],
            event_observed_B=group_b['event']
        )
        
        # Fit KM for each group
        kmf_a = KaplanMeierFitter()
        kmf_a.fit(group_a['survival_time_days'], group_a['event'], label=str(groups[0]))
        
        kmf_b = KaplanMeierFitter()
        kmf_b.fit(group_b['survival_time_days'], group_b['event'], label=str(groups[1]))
        
        return {
            'test_statistic': results.test_statistic,
            'p_value': results.p_value,
            'is_significant': results.p_value < 0.05,
            'group_a_median': kmf_a.median_survival_time_,
            'group_b_median': kmf_b.median_survival_time_,
            'survival_curves': {
                'group_a': kmf_a.survival_function_,
                'group_b': kmf_b.survival_function_
            }
        }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import os
    from datetime import datetime, timedelta
    
    # Configuration
    db_conn_string = os.getenv("DATABASE_URL")
    
    # Run ETL
    etl = RiskAnalyticsETL(db_conn_string)
    
    # Full refresh for last 90 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    etl.run_full_pipeline(start_date, end_date)
    etl.close()
    
    # Run survival analysis
    survival = SurvivalAnalysis(db_conn_string)
    
    # Kaplan-Meier for employee attrition
    km_results = survival.kaplan_meier_analysis('Employee Attrition')
    print("Kaplan-Meier Survival Function:")
    print(km_results.head(10))
    
    # Cox PH to identify risk factors
    cox_results = survival.cox_proportional_hazards('Employee Attrition')
    print("\nCox Proportional Hazards - Hazard Ratios:")
    print(cox_results['hazard_ratios'])
    
    # Compare intervention vs no intervention
    comparison = survival.compare_cohorts('Employee Attrition', 'intervention_applied')
    print(f"\nLog-rank test p-value: {comparison['p_value']:.4f}")
    print(f"Intervention median survival: {comparison['group_a_median']:.1f} days")
    print(f"No intervention median survival: {comparison['group_b_median']:.1f} days")
