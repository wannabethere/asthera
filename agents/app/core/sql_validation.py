"""
SQL Validation Service for validating SQL alert conditions

This module provides a reusable SQL validation service that can be used by
various agents to validate SQL-based conditions using existing execute_sql methods.
"""

import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Union, Protocol
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class AlertConditionType(str, Enum):
    """Types of alert conditions"""
    INTELLIGENT_ARIMA = "intelligent_arima"
    THRESHOLD_CHANGE = "threshold_change"
    THRESHOLD_PERCENT_CHANGE = "threshold_percent_change"
    THRESHOLD_ABSOLUTE_CHANGE = "threshold_absolute_change"
    THRESHOLD_VALUE = "threshold_value"
    STRING_MATCH = "string_match"
    REGEX_MATCH = "regex_match"
    ANOMALY_DETECTION = "anomaly_detection"
    TREND_ANALYSIS = "trend_analysis"


class ThresholdOperator(str, Enum):
    """Threshold operators for condition validation"""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUALS = "="
    NOT_EQUALS = "!="


class ThresholdType(str, Enum):
    """Types of threshold values for condition validation"""
    DEFAULT = "default"  # Direct value comparison
    PERCENTAGE = "percentage"  # Threshold as percentage (multiply by 100)
    RATIO = "ratio"  # Threshold as ratio (0-1 range)
    PERCENTILE = "percentile"  # Threshold as percentile (0-100 range)
    MULTIPLIER = "multiplier"  # Threshold as multiplier factor
    ABSOLUTE = "absolute"  # Threshold as absolute value


class ValidationResult(BaseModel):
    """Result of condition validation"""
    is_valid: bool
    current_value: Optional[Union[float, int]] = None
    threshold_value: Optional[Union[float, int]] = None
    condition_met: Optional[bool] = None
    error_message: Optional[str] = None
    validation_timestamp: datetime = Field(default_factory=datetime.now)
    execution_time_ms: Optional[float] = None


class SQLValidationService:
    """Service for validating SQL alert conditions using existing execute_sql methods"""
    
    def __init__(self, engine):
        """
        Initialize validation service with a database engine
        
        Args:
            engine: Database engine instance (PandasEngine, etc.) with execute_sql methods
        """
        self.engine = engine
    
    async def validate_threshold_condition(
        self,
        sql_query: str,
        condition_type: AlertConditionType,
        operator: ThresholdOperator,
        threshold_value: Union[float, int],
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a threshold-based alert condition by executing SQL and checking conditions
        
        Args:
            sql_query: SQL query to execute for validation
            condition_type: Type of condition to validate
            operator: Threshold operator (>, <, >=, <=, =, !=)
            threshold_value: Threshold value to compare against
            metric_column: Specific column to extract value from (if None, uses first numeric column)
            session: aiohttp session for async execution
            use_cache: Whether to use caching for SQL execution
            
        Returns:
            ValidationResult with validation details
        """
        start_time = datetime.now()
        
        try:
            # Execute the SQL query using existing engine methods
            if hasattr(self.engine, 'execute_sql') and asyncio.iscoroutinefunction(self.engine.execute_sql):
                # Use async execute_sql if available
                success, result = await self.engine.execute_sql(
                    sql=sql_query,
                    session=session,
                    dry_run=False,
                    use_cache=use_cache
                )
            else:
                # Use sync execute_sql_sync if available
                success, result = self.engine._execute_sql_sync(sql_query)
            
            if not success or not result:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"SQL execution failed: {result.get('error', 'Unknown error') if result else 'No result returned'}"
                )
            
            # Extract data from result
            data = result.get('data', [])
            if not data:
                return ValidationResult(
                    is_valid=False,
                    error_message="No data returned from SQL query"
                )
            
            # Get the current value from the first row
            first_row = data[0]
            
            # Determine which column to use for validation
            if metric_column and metric_column in first_row:
                current_value = first_row[metric_column]
            else:
                # Find first numeric column
                current_value = None
                for key, value in first_row.items():
                    if value is not None:
                        try:
                            # Try to convert to float (handles both numeric and string values)
                            current_value = float(value)
                            metric_column = key
                            break
                        except (ValueError, TypeError):
                            # Skip non-numeric values
                            continue
                
                if current_value is None:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"No numeric values found in result. Available columns: {list(first_row.keys())}, Sample values: {list(first_row.values())}"
                    )
            
            # Convert to numeric if needed
            try:
                current_value = float(current_value)
                threshold_value = float(threshold_value)
            except (ValueError, TypeError) as e:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid numeric values: current_value={current_value}, threshold_value={threshold_value}. Error: {str(e)}"
                )
            
            # Check if condition is met based on operator
            condition_met = self._evaluate_condition(current_value, operator, threshold_value)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ValidationResult(
                is_valid=True,
                current_value=current_value,
                threshold_value=threshold_value,
                condition_met=condition_met,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return ValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}",
                execution_time_ms=execution_time
            )
    
    def _evaluate_condition(
        self, 
        current_value: float, 
        operator: ThresholdOperator, 
        threshold_value: float
    ) -> bool:
        """Evaluate the threshold condition"""
        if operator == ThresholdOperator.GREATER_THAN:
            return current_value > threshold_value
        elif operator == ThresholdOperator.LESS_THAN:
            return current_value < threshold_value
        elif operator == ThresholdOperator.GREATER_EQUAL:
            return current_value >= threshold_value
        elif operator == ThresholdOperator.LESS_EQUAL:
            return current_value <= threshold_value
        elif operator == ThresholdOperator.EQUALS:
            return abs(current_value - threshold_value) < 1e-9  # Use small epsilon for float comparison
        elif operator == ThresholdOperator.NOT_EQUALS:
            return abs(current_value - threshold_value) >= 1e-9
        else:
            raise ValueError(f"Unsupported operator: {operator}")
    
    async def validate_percentage_condition(
        self,
        sql_query: str,
        operator: ThresholdOperator,
        threshold_percentage: float,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a percentage-based condition (e.g., completion rate < 90%)
        
        Args:
            sql_query: SQL query that returns percentage values
            operator: Threshold operator
            threshold_percentage: Threshold percentage value (0-100)
            metric_column: Column containing percentage values
            session: aiohttp session
            use_cache: Whether to use caching
            
        Returns:
            ValidationResult with validation details
        """
        # Ensure threshold is between 0 and 100
        if not (0 <= threshold_percentage <= 100):
            return ValidationResult(
                is_valid=False,
                error_message=f"Threshold percentage must be between 0 and 100, got: {threshold_percentage}"
            )
        
        return await self.validate_threshold_condition(
            sql_query=sql_query,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=operator,
            threshold_value=threshold_percentage,
            metric_column=metric_column,
            session=session,
            use_cache=use_cache
        )
    
    async def validate_change_condition(
        self,
        current_sql: str,
        previous_sql: str,
        operator: ThresholdOperator,
        change_threshold: float,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a change-based condition by comparing current vs previous values
        
        Args:
            current_sql: SQL query for current period
            previous_sql: SQL query for previous period
            operator: Threshold operator
            change_threshold: Threshold for absolute change
            metric_column: Column to compare
            session: aiohttp session
            use_cache: Whether to use caching
            
        Returns:
            ValidationResult with validation details
        """
        start_time = datetime.now()
        
        try:
            # Execute both queries
            current_result = await self._execute_sql_query(current_sql, session, use_cache)
            previous_result = await self._execute_sql_query(previous_sql, session, use_cache)
            
            if not current_result.is_valid or not previous_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Failed to execute queries. Current: {current_result.error_message}, Previous: {previous_result.error_message}"
                )
            
            current_value = current_result.current_value
            previous_value = previous_result.current_value
            
            # Calculate absolute change
            absolute_change = current_value - previous_value
            
            # Check if change condition is met
            condition_met = self._evaluate_condition(absolute_change, operator, change_threshold)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ValidationResult(
                is_valid=True,
                current_value=absolute_change,
                threshold_value=change_threshold,
                condition_met=condition_met,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return ValidationResult(
                is_valid=False,
                error_message=f"Change validation error: {str(e)}",
                execution_time_ms=execution_time
            )
    
    async def validate_percent_change_condition(
        self,
        current_sql: str,
        previous_sql: str,
        operator: ThresholdOperator,
        percent_change_threshold: float,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a percentage change condition (e.g., sales dropped by more than 10%)
        
        Args:
            current_sql: SQL query for current period
            previous_sql: SQL query for previous period
            operator: Threshold operator
            percent_change_threshold: Threshold for percentage change
            metric_column: Column to compare
            session: aiohttp session
            use_cache: Whether to use caching
            
        Returns:
            ValidationResult with validation details
        """
        start_time = datetime.now()
        
        try:
            # Execute both queries
            current_result = await self._execute_sql_query(current_sql, session, use_cache)
            previous_result = await self._execute_sql_query(previous_sql, session, use_cache)
            
            if not current_result.is_valid or not previous_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Failed to execute queries. Current: {current_result.error_message}, Previous: {previous_result.error_message}"
                )
            
            current_value = current_result.current_value
            previous_value = previous_result.current_value
            
            # Calculate percentage change
            if previous_value == 0:
                percent_change = 100.0 if current_value > 0 else 0.0
            else:
                percent_change = ((current_value - previous_value) / previous_value) * 100
            
            # Check if percentage change condition is met
            condition_met = self._evaluate_condition(percent_change, operator, percent_change_threshold)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ValidationResult(
                is_valid=True,
                current_value=percent_change,
                threshold_value=percent_change_threshold,
                condition_met=condition_met,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return ValidationResult(
                is_valid=False,
                error_message=f"Percent change validation error: {str(e)}",
                execution_time_ms=execution_time
            )
    
    async def _execute_sql_query(
        self,
        sql_query: str,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """Helper method to execute SQL and return ValidationResult"""
        try:
            if hasattr(self.engine, 'execute_sql') and asyncio.iscoroutinefunction(self.engine.execute_sql):
                success, result = await self.engine.execute_sql(
                    sql=sql_query,
                    session=session,
                    dry_run=False,
                    use_cache=use_cache
                )
            else:
                success, result = self.engine._execute_sql_sync(sql_query)
            
            if not success or not result:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"SQL execution failed: {result.get('error', 'Unknown error') if result else 'No result returned'}"
                )
            
            data = result.get('data', [])
            if not data:
                return ValidationResult(
                    is_valid=False,
                    error_message="No data returned from SQL query"
                )
            
            # Get first numeric value
            first_row = data[0]
            current_value = None
            for key, value in first_row.items():
                if value is not None:
                    try:
                        # Try to convert to float (handles both numeric and string values)
                        current_value = float(value)
                        break
                    except (ValueError, TypeError):
                        # Skip non-numeric values
                        continue
            
            if current_value is None:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"No numeric values found in result. Available columns: {list(first_row.keys())}, Sample values: {list(first_row.values())}"
                )
            
            return ValidationResult(
                is_valid=True,
                current_value=current_value
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"SQL execution error: {str(e)}"
            )
    
    async def validate_condition_by_type(
        self,
        sql_query: str,
        condition_type: AlertConditionType,
        operator: ThresholdOperator,
        threshold_value: Union[float, int],
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a condition by automatically selecting the appropriate validation method based on type
        
        Args:
            sql_query: SQL query to execute for validation
            condition_type: Type of condition to validate
            operator: Threshold operator
            threshold_value: Threshold value to compare against
            metric_column: Specific column to extract value from
            session: aiohttp session for async execution
            use_cache: Whether to use caching for SQL execution
            
        Returns:
            ValidationResult with validation details
        """
        if condition_type == AlertConditionType.THRESHOLD_VALUE:
            return await self.validate_threshold_condition(
                sql_query=sql_query,
                condition_type=condition_type,
                operator=operator,
                threshold_value=threshold_value,
                metric_column=metric_column,
                session=session,
                use_cache=use_cache
            )
        elif condition_type in [AlertConditionType.THRESHOLD_CHANGE, AlertConditionType.THRESHOLD_ABSOLUTE_CHANGE]:
            # For change conditions, we need separate current and previous SQL queries
            return ValidationResult(
                is_valid=False,
                error_message=f"Change-based conditions require separate current and previous SQL queries. Use validate_change_condition() or validate_percent_change_condition() instead."
            )
        elif condition_type == AlertConditionType.THRESHOLD_PERCENT_CHANGE:
            # For percentage change conditions, we need separate current and previous SQL queries
            return ValidationResult(
                is_valid=False,
                error_message=f"Percentage change conditions require separate current and previous SQL queries. Use validate_percent_change_condition() instead."
            )
        elif condition_type == AlertConditionType.INTELLIGENT_ARIMA:
            # ARIMA conditions require historical data analysis - not suitable for simple validation
            return ValidationResult(
                is_valid=False,
                error_message=f"ARIMA conditions require historical data analysis and cannot be validated with simple threshold checks."
            )
        else:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unsupported condition type: {condition_type}"
            )



# Additional models for alert-specific validation
class LexyFeedCondition(BaseModel):
    """Lexy Feed condition configuration"""
    condition_type: AlertConditionType
    threshold_type: Optional[str] = None  # For threshold-based conditions
    operator: Optional[ThresholdOperator] = None
    value: Optional[Union[float, int]] = None


class LexyFeedMetric(BaseModel):
    """Lexy Feed metric configuration"""
    domain: str
    dataset_id: str
    measure: str
    aggregation: str
    resolution: str = "Daily"  # Daily, Weekly, Monthly, Quarterly, Yearly
    filters: List[Dict[str, Any]] = []
    drilldown_dimensions: List[str] = []


class LexyFeedNotification(BaseModel):
    """Lexy Feed notification settings"""
    schedule_type: str
    metric_name: str
    email_addresses: List[str] = []
    subject: str
    email_message: str
    include_feed_report: bool = True
    custom_schedule: Optional[Dict[str, Any]] = None


class LexyFeedConfiguration(BaseModel):
    """Complete Lexy Feed configuration"""
    metric: LexyFeedMetric
    condition: LexyFeedCondition
    notification: LexyFeedNotification
    column_selection: Dict[str, List[str]]  # included/excluded columns


class SQLAlertConditionValidator:
    """Convenience wrapper for SQL validation service with LexyFeedCondition support"""
    
    def __init__(self, engine):
        """
        Initialize validator with a database engine
        
        Args:
            engine: Database engine instance (PandasEngine, etc.) with execute_sql methods
        """
        self.validation_service = SQLValidationService(engine)
    
    async def validate_threshold_condition(
        self,
        sql_query: str,
        condition_type: AlertConditionType,
        operator: ThresholdOperator,
        threshold_value: Union[float, int],
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """Validate a threshold-based alert condition"""
        return await self.validation_service.validate_threshold_condition(
            sql_query=sql_query,
            condition_type=condition_type,
            operator=operator,
            threshold_value=threshold_value,
            metric_column=metric_column,
            session=session,
            use_cache=use_cache
        )
    
    async def validate_percentage_condition(
        self,
        sql_query: str,
        operator: ThresholdOperator,
        threshold_percentage: float,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """Validate a percentage-based condition"""
        return await self.validation_service.validate_percentage_condition(
            sql_query=sql_query,
            operator=operator,
            threshold_percentage=threshold_percentage,
            metric_column=metric_column,
            session=session,
            use_cache=use_cache
        )
    
    async def validate_change_condition(
        self,
        current_sql: str,
        previous_sql: str,
        operator: ThresholdOperator,
        change_threshold: float,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """Validate a change-based condition"""
        return await self.validation_service.validate_change_condition(
            current_sql=current_sql,
            previous_sql=previous_sql,
            operator=operator,
            change_threshold=change_threshold,
            metric_column=metric_column,
            session=session,
            use_cache=use_cache
        )
    
    async def validate_percent_change_condition(
        self,
        current_sql: str,
        previous_sql: str,
        operator: ThresholdOperator,
        percent_change_threshold: float,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """Validate a percentage change condition"""
        return await self.validation_service.validate_percent_change_condition(
            current_sql=current_sql,
            previous_sql=previous_sql,
            operator=operator,
            percent_change_threshold=percent_change_threshold,
            metric_column=metric_column,
            session=session,
            use_cache=use_cache
        )
    
    async def validate_condition(
        self,
        sql_query: str,
        condition: LexyFeedCondition,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a LexyFeedCondition by automatically selecting the appropriate validation method
        
        Args:
            sql_query: SQL query to execute for validation
            condition: LexyFeedCondition object to validate
            metric_column: Specific column to extract value from
            session: aiohttp session for async execution
            use_cache: Whether to use caching for SQL execution
            
        Returns:
            ValidationResult with validation details
        """
        if condition.condition_type == AlertConditionType.THRESHOLD_VALUE:
            return await self.validation_service.validate_threshold_condition(
                sql_query=sql_query,
                condition_type=condition.condition_type,
                operator=condition.operator,
                threshold_value=condition.value,
                metric_column=metric_column,
                session=session,
                use_cache=use_cache
            )
        elif condition.condition_type in [AlertConditionType.THRESHOLD_CHANGE, AlertConditionType.THRESHOLD_ABSOLUTE_CHANGE]:
            # For change conditions, we need separate current and previous SQL queries
            return ValidationResult(
                is_valid=False,
                error_message=f"Change-based conditions require separate current and previous SQL queries. Use validate_change_condition() or validate_percent_change_condition() instead."
            )
        elif condition.condition_type == AlertConditionType.THRESHOLD_PERCENT_CHANGE:
            # For percentage change conditions, we need separate current and previous SQL queries
            return ValidationResult(
                is_valid=False,
                error_message=f"Percentage change conditions require separate current and previous SQL queries. Use validate_percent_change_condition() instead."
            )
        elif condition.condition_type == AlertConditionType.INTELLIGENT_ARIMA:
            # ARIMA conditions require historical data analysis - not suitable for simple validation
            return ValidationResult(
                is_valid=False,
                error_message=f"ARIMA conditions require historical data analysis and cannot be validated with simple threshold checks."
            )
        else:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unsupported condition type: {condition.condition_type}"
            )
    
    async def validate_feed_configuration(
        self,
        sql_query: str,
        feed_config: LexyFeedConfiguration,
        metric_column: str = None,
        session: aiohttp.ClientSession = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a complete LexyFeedConfiguration by validating its condition
        
        Args:
            sql_query: SQL query to execute for validation
            feed_config: LexyFeedConfiguration object to validate
            metric_column: Specific column to extract value from
            session: aiohttp session for async execution
            use_cache: Whether to use caching for SQL execution
            
        Returns:
            ValidationResult with validation details
        """
        return await self.validate_condition(
            sql_query=sql_query,
            condition=feed_config.condition,
            metric_column=metric_column,
            session=session,
            use_cache=use_cache
        )

# Convenience function for creating a validation service
def create_sql_validation_service(engine) -> SQLValidationService:
    """
    Create a SQL validation service with the provided engine
    
    Args:
        engine: Database engine instance with execute_sql methods
        
    Returns:
        SQLValidationService instance
    """
    return SQLValidationService(engine)



