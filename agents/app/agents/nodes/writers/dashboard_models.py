from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum


class FilterOperator(Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    REGEX = "regex"


class FilterType(Enum):
    COLUMN_FILTER = "column_filter"
    TIME_FILTER = "time_filter"
    CONDITIONAL_FORMAT = "conditional_format"
    AGGREGATION_FILTER = "aggregation_filter"
    CUSTOM_FILTER = "custom_filter"


class ActionType(Enum):
    SQL_EXPANSION = "sql_expansion"
    CHART_ADJUSTMENT = "chart_adjustment"
    BOTH = "both"


@dataclass
class ControlFilter:
    """Represents a single control filter configuration"""
    filter_id: str
    filter_type: FilterType
    column_name: str
    operator: FilterOperator
    value: Union[str, int, float, List, Dict]
    condition: Optional[str] = None
    description: Optional[str] = None
    
    def to_sql_condition(self) -> str:
        """Convert filter to SQL WHERE condition"""
        if self.operator == FilterOperator.EQUALS:
            return f"{self.column_name} = '{self.value}'"
        elif self.operator == FilterOperator.NOT_EQUALS:
            return f"{self.column_name} != '{self.value}'"
        elif self.operator == FilterOperator.GREATER_THAN:
            return f"{self.column_name} > {self.value}"
        elif self.operator == FilterOperator.LESS_THAN:
            return f"{self.column_name} < {self.value}"
        elif self.operator == FilterOperator.GREATER_EQUAL:
            return f"{self.column_name} >= {self.value}"
        elif self.operator == FilterOperator.LESS_EQUAL:
            return f"{self.column_name} <= {self.value}"
        elif self.operator == FilterOperator.CONTAINS:
            return f"{self.column_name} LIKE '%{self.value}%'"
        elif self.operator == FilterOperator.NOT_CONTAINS:
            return f"{self.column_name} NOT LIKE '%{self.value}%'"
        elif self.operator == FilterOperator.STARTS_WITH:
            return f"{self.column_name} LIKE '{self.value}%'"
        elif self.operator == FilterOperator.ENDS_WITH:
            return f"{self.column_name} LIKE '%{self.value}'"
        elif self.operator == FilterOperator.IN:
            values = "', '".join(str(v) for v in self.value)
            return f"{self.column_name} IN ('{values}')"
        elif self.operator == FilterOperator.NOT_IN:
            values = "', '".join(str(v) for v in self.value)
            return f"{self.column_name} NOT IN ('{values}')"
        elif self.operator == FilterOperator.BETWEEN:
            return f"{self.column_name} BETWEEN {self.value[0]} AND {self.value[1]}"
        elif self.operator == FilterOperator.IS_NULL:
            return f"{self.column_name} IS NULL"
        elif self.operator == FilterOperator.IS_NOT_NULL:
            return f"{self.column_name} IS NOT NULL"
        elif self.operator == FilterOperator.REGEX:
            return f"{self.column_name} ~ '{self.value}'"
        else:
            return self.condition or ""


@dataclass
class ConditionalFormat:
    """Represents conditional formatting rules for charts"""
    format_id: str
    chart_id: str
    condition: ControlFilter
    formatting_rules: Dict[str, Any]
    description: Optional[str] = None
    
    def to_chart_adjustment_config(self) -> Dict[str, Any]:
        """Convert to chart adjustment configuration"""
        return {
            "adjustment_type": "conditional_format",
            "condition": asdict(self.condition),
            "formatting": self.formatting_rules,
            "description": self.description
        }


@dataclass
class DashboardConfiguration:
    """Complete dashboard configuration with all filters and formats"""
    dashboard_id: str
    filters: List[ControlFilter]
    conditional_formats: List[ConditionalFormat]
    time_filters: Optional[Dict[str, Any]] = None
    global_context: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, ActionType]] = None
    
    def get_chart_configurations(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration for each chart with action tags"""
        configurations = {}
        
        for conditional_format in self.conditional_formats:
            chart_id = conditional_format.chart_id
            if chart_id not in configurations:
                configurations[chart_id] = {
                    "chart_id": chart_id,
                    "sql_expansion": {},
                    "chart_adjustment": {},
                    "filters": [],
                    "actions": []
                }
            
            # Add conditional formatting
            configurations[chart_id]["chart_adjustment"].update(
                conditional_format.to_chart_adjustment_config()
            )
            configurations[chart_id]["actions"].append(ActionType.CHART_ADJUSTMENT.value)
        
        # Add global filters to SQL expansion for all charts
        global_sql_conditions = []
        for filter_obj in self.filters:
            sql_condition = filter_obj.to_sql_condition()
            if sql_condition:
                global_sql_conditions.append(sql_condition)
        
        if global_sql_conditions:
            for chart_id in configurations:
                configurations[chart_id]["sql_expansion"]["where_conditions"] = global_sql_conditions
                if ActionType.SQL_EXPANSION.value not in configurations[chart_id]["actions"]:
                    configurations[chart_id]["actions"].append(ActionType.SQL_EXPANSION.value)
        
        # Add time filters
        if self.time_filters:
            for chart_id in configurations:
                configurations[chart_id]["sql_expansion"]["time_filters"] = self.time_filters
                if ActionType.SQL_EXPANSION.value not in configurations[chart_id]["actions"]:
                    configurations[chart_id]["actions"].append(ActionType.SQL_EXPANSION.value)
        
        return configurations
