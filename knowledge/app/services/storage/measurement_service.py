"""
Storage service for ComplianceMeasurement and ControlRiskAnalytics
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.storage.models import ComplianceMeasurement, ControlRiskAnalytics
from app.storage.database import DatabaseClient

logger = logging.getLogger(__name__)


class MeasurementStorageService:
    """Service for managing compliance measurements and analytics"""
    
    def __init__(self, db_client: DatabaseClient):
        """Initialize with database client"""
        self.db_client = db_client
    
    async def save_measurement(self, measurement: ComplianceMeasurement) -> int:
        """Save a compliance measurement"""
        result = await self.db_client.fetchrow("""
            INSERT INTO compliance_measurements (
                control_id, measured_value, measurement_date, passed,
                context_id, data_source, measurement_method, quality_score
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING measurement_id
        """,
            measurement.control_id,
            measurement.measured_value,
            measurement.measurement_date or datetime.utcnow(),
            measurement.passed,
            measurement.context_id,
            measurement.data_source,
            measurement.measurement_method,
            measurement.quality_score
        )
        
        return result["measurement_id"]
    
    async def save_measurements(self, measurements: List[ComplianceMeasurement]) -> List[int]:
        """Save multiple measurements"""
        ids = []
        for measurement in measurements:
            try:
                measurement_id = await self.save_measurement(measurement)
                ids.append(measurement_id)
            except Exception as e:
                logger.error(f"Error saving measurement: {str(e)}")
        return ids
    
    async def get_measurements_for_control(
        self,
        control_id: str,
        context_id: Optional[str] = None,
        days: Optional[int] = None
    ) -> List[ComplianceMeasurement]:
        """Get measurements for a control"""
        query = """
            SELECT 
                measurement_id, control_id, measured_value, measurement_date,
                passed, context_id, data_source, measurement_method,
                quality_score, created_at
            FROM compliance_measurements
            WHERE control_id = $1
        """
        params = [control_id]
        
        if context_id:
            query += " AND context_id = $2"
            params.append(context_id)
        
        if days:
            query += f" AND measurement_date >= NOW() - INTERVAL '{days} days'"
        
        query += " ORDER BY measurement_date DESC"
        
        rows = await self.db_client.fetch(query, *params)
        
        return [
            ComplianceMeasurement(
                measurement_id=row["measurement_id"],
                control_id=row["control_id"],
                measured_value=float(row["measured_value"]) if row["measured_value"] else None,
                measurement_date=row["measurement_date"],
                passed=row["passed"],
                context_id=row["context_id"],
                data_source=row["data_source"],
                measurement_method=row["measurement_method"],
                quality_score=float(row["quality_score"]) if row["quality_score"] else None,
                created_at=row["created_at"]
            )
            for row in rows
        ]
    
    async def get_risk_analytics(self, control_id: str) -> Optional[ControlRiskAnalytics]:
        """Get risk analytics for a control"""
        row = await self.db_client.fetchrow("""
            SELECT 
                control_id, avg_compliance_score, trend,
                last_failure_date, failure_count_30d, failure_count_90d,
                current_risk_score, risk_level, updated_at
            FROM control_risk_analytics
            WHERE control_id = $1
        """, control_id)
        
        if row:
            return ControlRiskAnalytics(
                control_id=row["control_id"],
                avg_compliance_score=float(row["avg_compliance_score"]) if row["avg_compliance_score"] else None,
                trend=row["trend"],
                last_failure_date=row["last_failure_date"],
                failure_count_30d=row["failure_count_30d"] or 0,
                failure_count_90d=row["failure_count_90d"] or 0,
                current_risk_score=float(row["current_risk_score"]) if row["current_risk_score"] else None,
                risk_level=row["risk_level"],
                updated_at=row["updated_at"]
            )
        return None
    
    async def get_risk_analytics_batch(self, control_ids: List[str]) -> Dict[str, ControlRiskAnalytics]:
        """Get risk analytics for multiple controls"""
        rows = await self.db_client.fetch("""
            SELECT 
                control_id, avg_compliance_score, trend,
                last_failure_date, failure_count_30d, failure_count_90d,
                current_risk_score, risk_level, updated_at
            FROM control_risk_analytics
            WHERE control_id = ANY($1)
        """, control_ids)
        
        analytics = {}
        for row in rows:
            analytics[row["control_id"]] = ControlRiskAnalytics(
                control_id=row["control_id"],
                avg_compliance_score=float(row["avg_compliance_score"]) if row["avg_compliance_score"] else None,
                trend=row["trend"],
                last_failure_date=row["last_failure_date"],
                failure_count_30d=row["failure_count_30d"] or 0,
                failure_count_90d=row["failure_count_90d"] or 0,
                current_risk_score=float(row["current_risk_score"]) if row["current_risk_score"] else None,
                risk_level=row["risk_level"],
                updated_at=row["updated_at"]
            )
        
        return analytics

