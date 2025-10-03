from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel, RunnableBranch
from langchain_core.documents import Document
from app.indexing.alert_knowledge_helper import get_alert_knowledge_helper

import json
import uuid
import re
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Tuple, Union, Protocol
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import sqlparse
from sqlparse.sql import Statement, Token, TokenList
from sqlparse.tokens import Keyword, Name
from app.core.dependencies import create_llm_instances_from_settings
from app.agents.nodes.writers.alert_models import LexyFeedConfiguration, LexyFeedMetric, LexyFeedCondition, LexyFeedNotification, SQLAnalysis, SQLAlertResult, SQLAlertRequest, AlertConditionType, ThresholdOperator, ScheduleType
from app.core.sql_validation import SQLAlertConditionValidator, ValidationResult


class MarkdownJsonOutputParser(JsonOutputParser):
    """Custom JSON parser that can extract JSON from markdown-formatted responses and handle comments"""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse JSON from text that may contain markdown formatting and comments"""
        try:
            # First try to parse as pure JSON
            return super().parse(text)
        except Exception:
            # If that fails, try to extract and clean JSON from markdown
            try:
                # Look for JSON in code blocks
                json_pattern = r'```json\s*(.*?)\s*```'
                match = re.search(json_pattern, text, re.DOTALL)
                
                if match:
                    json_text = match.group(1)
                else:
                    # Look for JSON objects directly (more flexible)
                    json_pattern = r'\{.*\}'
                    match = re.search(json_pattern, text, re.DOTALL)
                    
                    if match:
                        json_text = match.group(0)
                    else:
                        raise ValueError("No valid JSON found in response")
                
                # Clean the JSON text by removing comments and fixing enum values
                cleaned_json = self._clean_json_text(json_text)
                
                return json.loads(cleaned_json)
                
            except Exception as e:
                raise ValueError(f"Failed to parse JSON from markdown response: {e}")
    
    def _clean_json_text(self, json_text: str) -> str:
        """Clean JSON text by removing comments and fixing common issues"""
        # Remove single-line comments (// comments)
        lines = json_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove comments but preserve the line structure
            if '//' in line:
                # Find the // and remove everything after it, but keep the line if it has content before //
                comment_pos = line.find('//')
                if comment_pos > 0:
                    # Check if there's actual content before the comment
                    content_before_comment = line[:comment_pos].strip()
                    if content_before_comment and not content_before_comment.endswith(','):
                        # Add comma if the line ends with content but no comma
                        cleaned_lines.append(content_before_comment + ',')
                    elif content_before_comment:
                        cleaned_lines.append(content_before_comment)
                # If the line starts with //, skip it entirely
            else:
                cleaned_lines.append(line)
        
        # Join the lines back together
        cleaned_json = '\n'.join(cleaned_lines)
        
        # Fix enum values that are wrapped in angle brackets
        cleaned_json = re.sub(r'<(\w+)\.(\w+):\s*[\'"](\w+)[\'"]\s*>', r'"\3"', cleaned_json)
        
        # Remove trailing commas before closing braces/brackets
        cleaned_json = re.sub(r',\s*([}\]])', r'\1', cleaned_json)
        
        # Fix any remaining issues with null values
        cleaned_json = cleaned_json.replace('null', 'null')
        
        return cleaned_json


# Protocol for LLM interface
class LLMProtocol(Protocol):
    """Protocol for LLM instances that can be used with the agent"""
    def invoke(self, input: Any) -> Any: ...
    async def ainvoke(self, input: Any) -> Any: ...





class SQLToAlertAgent:
    """Self-RAG Agent for converting SQL + Natural Language to Lexy Feed Alerts
    
    This agent requires LLM instances to be provided as input parameters, allowing for
    flexible configuration and external settings management. The LLM instances should
    implement the LLMProtocol interface.
    
    Args:
        sql_parser_llm: LLM instance for parsing and analyzing SQL queries
        alert_generator_llm: LLM instance for generating alert configurations
        critic_llm: LLM instance for critiquing generated configurations
        refiner_llm: LLM instance for refining configurations based on critique
    """
    
    def __init__(self, sql_parser_llm=None, alert_generator_llm=None, critic_llm=None, refiner_llm=None):
        # Use provided LLM instances or create default ones
        if sql_parser_llm is None or alert_generator_llm is None or critic_llm is None or refiner_llm is None:
            sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm = create_llm_instances_from_settings()
        
        self.sql_parser_llm = sql_parser_llm
        self.alert_generator_llm = alert_generator_llm
        self.critic_llm = critic_llm
        self.refiner_llm = refiner_llm
        
        # Initialize knowledge base helper
        self.knowledge_helper = get_alert_knowledge_helper()
        
        # Session storage
        self.sessions = {}
        
        # Build Self-RAG pipeline
        self.pipeline = self._build_pipeline()
    
    
    def _fix_enum_values(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Fix enum values and data type issues in configuration dictionary"""
        import re
        
        # Helper function to extract enum value from string representation
        def extract_enum_value(value_str: str, enum_class) -> str:
            if isinstance(value_str, str) and '<' in value_str and '>' in value_str:
                # Extract the actual value from string like "<AlertConditionType.THRESHOLD_VALUE: 'threshold_value'>"
                match = re.search(r": '([^']+)'", value_str)
                if match:
                    return match.group(1)
            return value_str
        
        # Helper function to map enum names to values and handle invalid values
        def map_enum_value(value_str: str, enum_class, default_value: str = None) -> str:
            if not isinstance(value_str, str):
                return default_value or list(enum_class)[0].value
            
            # First try to find by value
            for enum_item in enum_class:
                if enum_item.value == value_str:
                    return value_str
            
            # Then try to find by name
            for enum_item in enum_class:
                if enum_item.name == value_str:
                    return enum_item.value
            
            # Handle common mappings for AlertConditionType
            if enum_class == AlertConditionType:
                mapping = {
                    'THRESHOLD_STATIC': 'threshold_value',
                    'STATIC_THRESHOLD': 'threshold_value',
                    'VALUE_THRESHOLD': 'threshold_value',
                    'THRESHOLD': 'threshold_value'
                }
                if value_str in mapping:
                    return mapping[value_str]
            
            # Handle common mappings for ThresholdOperator
            if enum_class == ThresholdOperator:
                mapping = {
                    'GREATER_THAN': '>',
                    'LESS_THAN': '<',
                    'GREATER_EQUAL': '>=',
                    'LESS_EQUAL': '<=',
                    'EQUALS': '=',
                    'NOT_EQUALS': '!=',
                    'GT': '>',
                    'LT': '<',
                    'GTE': '>=',
                    'LTE': '<=',
                    'EQ': '=',
                    'NE': '!='
                }
                if value_str in mapping:
                    return mapping[value_str]
            
            # Return default value if no match found
            return default_value or list(enum_class)[0].value
        
        # Helper function to convert list to string (take first element or join)
        def list_to_string(value, field_name: str = "") -> str:
            if isinstance(value, list):
                if len(value) == 0:
                    return ""
                elif len(value) == 1:
                    return str(value[0])
                else:
                    # For multiple values, join them or take the first one based on field
                    if field_name in ["measure", "aggregation"]:
                        return str(value[0])  # Take first for single-value fields
                    else:
                        return ", ".join(str(v) for v in value)
            return str(value) if value is not None else ""
        
        # Fix conditions (support both single condition and multiple conditions)
        if "conditions" in config_dict:
            # Handle multiple conditions
            for condition in config_dict["conditions"]:
                if "condition_type" in condition:
                    condition["condition_type"] = map_enum_value(
                        condition["condition_type"], 
                        AlertConditionType,
                        "threshold_value"  # Default fallback
                    )
                if "operator" in condition:
                    condition["operator"] = map_enum_value(
                        condition["operator"], 
                        ThresholdOperator,
                        ">"  # Default fallback
                    )
        elif "condition" in config_dict:
            # Handle single condition for backward compatibility
            if "condition_type" in config_dict["condition"]:
                config_dict["condition"]["condition_type"] = map_enum_value(
                    config_dict["condition"]["condition_type"], 
                    AlertConditionType,
                    "threshold_value"  # Default fallback
                )
            if "operator" in config_dict["condition"]:
                config_dict["condition"]["operator"] = map_enum_value(
                    config_dict["condition"]["operator"], 
                    ThresholdOperator,
                    ">"  # Default fallback
                )
        
        # Fix schedule_type
        if "notification" in config_dict and "schedule_type" in config_dict["notification"]:
            config_dict["notification"]["schedule_type"] = map_enum_value(
                config_dict["notification"]["schedule_type"], 
                ScheduleType,
                "scheduled"  # Default fallback
            )
        
        # Fix metric fields that should be strings
        if "metric" in config_dict:
            metric = config_dict["metric"]
            
            # Fix measure field (should be string, not list)
            if "measure" in metric:
                metric["measure"] = list_to_string(metric["measure"], "measure")
            
            # Fix aggregation field (should be string, not list)
            if "aggregation" in metric:
                metric["aggregation"] = list_to_string(metric["aggregation"], "aggregation")
            
            # Fix domain field (should be string, not list)
            if "domain" in metric:
                metric["domain"] = list_to_string(metric["domain"], "domain")
            
            # Fix dataset_id field (should be string, not list)
            if "dataset_id" in metric:
                metric["dataset_id"] = list_to_string(metric["dataset_id"], "dataset_id")
            
            # Fix resolution field (should be string, not list)
            if "resolution" in metric:
                metric["resolution"] = list_to_string(metric["resolution"], "resolution")
        
        # Fix notification fields that should be strings
        if "notification" in config_dict:
            notification = config_dict["notification"]
            
            # Fix metric_name field (should be string, not list)
            if "metric_name" in notification:
                notification["metric_name"] = list_to_string(notification["metric_name"], "metric_name")
            
            # Fix subject field (should be string, not list)
            if "subject" in notification:
                notification["subject"] = list_to_string(notification["subject"], "subject")
            
            # Fix email_message field (should be string, not list)
            if "email_message" in notification:
                notification["email_message"] = list_to_string(notification["email_message"], "email_message")
            
            # Fix custom_schedule field (should be dict or None, not string)
            if "custom_schedule" in notification:
                custom_schedule = notification["custom_schedule"]
                if isinstance(custom_schedule, str):
                    # Convert string to a proper schedule dict or set to None
                    if custom_schedule.strip():
                        notification["custom_schedule"] = {
                            "description": custom_schedule,
                            "schedule": custom_schedule,
                            "timezone": "UTC"
                        }
                    else:
                        notification["custom_schedule"] = None
                elif not isinstance(custom_schedule, dict) and custom_schedule is not None:
                    # If it's not a string or dict, set to None
                    notification["custom_schedule"] = None
        
        # Fix condition fields that should be strings
        if "condition" in config_dict:
            condition = config_dict["condition"]
            
            # Fix threshold_type field (should be string, not list)
            if "threshold_type" in condition:
                condition["threshold_type"] = list_to_string(condition["threshold_type"], "threshold_type")
        
        # Ensure all required fields have default values
        self._ensure_default_values(config_dict)
        
        return config_dict
    
    def _ensure_default_values(self, config_dict: Dict[str, Any]) -> None:
        """Ensure all required fields have appropriate default values"""
        
        # Ensure notification has default values
        if "notification" in config_dict:
            notification = config_dict["notification"]
            
            # Set default custom_schedule if missing or None
            if "custom_schedule" not in notification or notification["custom_schedule"] is None:
                notification["custom_schedule"] = None
            
            # Set default email_addresses if missing
            if "email_addresses" not in notification:
                notification["email_addresses"] = []
            
            # Set default include_feed_report if missing
            if "include_feed_report" not in notification:
                notification["include_feed_report"] = True
        
        # Ensure metric has default values
        if "metric" in config_dict:
            metric = config_dict["metric"]
            
            # Set default drilldown_dimensions if missing
            if "drilldown_dimensions" not in metric:
                metric["drilldown_dimensions"] = []
            
            # Set default filters if missing
            if "filters" not in metric:
                metric["filters"] = []
        
        # Ensure column_selection has default values
        if "column_selection" not in config_dict:
            config_dict["column_selection"] = {
                "included": [],
                "excluded": []
            }
        else:
            column_selection = config_dict["column_selection"]
            if "included" not in column_selection:
                column_selection["included"] = []
            if "excluded" not in column_selection:
                column_selection["excluded"] = []

    def _build_pipeline(self):
        """Build Self-RAG pipeline for SQL-to-Alert generation"""
        
        # Step 1: Parse SQL and retrieve context
        sql_analysis_chain = (
            RunnablePassthrough.assign(
                sql_analysis=RunnableLambda(self._analyze_sql),
                domain_context=RunnableLambda(self._retrieve_domain_context)
            )
        )
        
        # Step 2: Generate alert configuration
        alert_generation_chain = (
            sql_analysis_chain
            | RunnablePassthrough.assign(
                feed_configuration=RunnableLambda(self._generate_feed_configuration)
            )
        )
        
        # Step 3: Critique the generated alert
        critique_chain = (
            alert_generation_chain
            | RunnablePassthrough.assign(
                critique=RunnableLambda(self._critique_alert_configuration)
            )
        )
        
        # Step 4: Refine based on critique
        refinement_chain = (
            critique_chain
            | RunnableLambda(self._refine_alert_configuration)
        )
        
        return refinement_chain
    
    async def _analyze_sql(self, inputs: Dict) -> SQLAnalysis:
        """Parse and analyze SQL query to extract relevant components"""
        
        request = inputs["request"]
        sql = request.sql
        
        # Use sqlparse for basic parsing
        parsed = sqlparse.parse(sql)[0]
        
        # Extract components using LLM for more intelligent parsing
        sql_analysis_prompt = ChatPromptTemplate.from_template("""
Analyze the following SQL query and extract key components for alert generation:

SQL: {sql}
Natural Language Query: {query}

Extract and return JSON with:
{{
    "tables": ["list of table names"],
    "columns": ["list of all columns referenced"],
    "metrics": ["list of calculated/derived metrics with aggregations"],
    "dimensions": ["list of GROUP BY columns that could be used for breakdowns"],
    "filters": [{{
        "column": "column_name",
        "condition": "condition_type", 
        "value": "filter_value"
    }}],
    "aggregations": [{{
        "column": "column_name",
        "function": "aggregation_function",
        "alias": "column_alias"
    }}],
}}

Focus on identifying:
1. Metrics that could be tracked (counts, percentages, averages)
2. Dimensions for breaking down alerts (training_type, department, etc.)
3. Existing filters that define the scope
4. Calculated fields that represent KPIs
""")
        
        chain = sql_analysis_prompt | self.sql_parser_llm | JsonOutputParser()
        
        analysis_result = await chain.ainvoke({
            "sql": sql,
            "query": request.query
        })
        
        return SQLAnalysis(**analysis_result)
    
    async def _retrieve_domain_context(self, inputs: Dict) -> List[str]:
        """Retrieve relevant domain knowledge for alert generation"""
        
        request = inputs["request"]
        
        # Search for relevant knowledge using the knowledge helper
        query_text = f"{request.query} {request.alert_request}"
        knowledge_content = self.knowledge_helper.search_knowledge(
            query=query_text, 
            k=5, 
            search_type="semantic"
        )
        
        return knowledge_content
    
    async def _generate_feed_configuration(self, inputs: Dict) -> LexyFeedConfiguration:
        """Generate Lexy Feed configuration from SQL analysis and alert request"""
        
        request = inputs["request"]
        sql_analysis = inputs["sql_analysis"]
        domain_context = inputs["domain_context"]
        sample_data = request.sample_data
        
        # Prepare enhanced sample data context for the prompt
        sample_data_context = ""
        if sample_data and sample_data.get("data"):
            data = sample_data.get("data", [])
            columns = sample_data.get('columns', [])
            
            # Analyze data patterns for better alert generation
            data_analysis = self._analyze_sample_data(data, columns)
            
            sample_data_context = f"""
Sample Data from SQL Execution:
- Columns: {columns}
- Sample Rows (first 5): {data[:5]}
- Total Sample Size: {len(data)}
- Data Analysis: {data_analysis}

Use this sample data to:
1. Set realistic threshold values based on actual data ranges and patterns
2. Choose appropriate condition types based on data distribution and variance
3. Validate that the metric selection makes sense with the actual data structure
4. Set appropriate resolution (Daily/Weekly/Monthly) based on data frequency and business context
5. Generate meaningful alert names and descriptions based on actual data values
6. Set appropriate operators (>, <, =, etc.) based on data trends and business logic
"""
        
        generation_prompt = ChatPromptTemplate.from_template("""
You are an expert in generating Lexy Feed alert configurations. Based on the SQL analysis, alert request, and sample data, create a comprehensive Feed configuration.

SQL Analysis:
- Tables: {tables}
- Metrics: {metrics}
- Dimensions: {dimensions}
- Filters: {filters}
- Aggregations: {aggregations}

Alert Request: {alert_request}
Original Query: {query}
Domain Context: {domain_context}
{sample_data_context}

IMPORTANT: You must respond with ONLY valid JSON. Do not include any markdown formatting, comments, or explanatory text. The response must be parseable JSON.

Generate a JSON Feed configuration:
{{
    "metric": {{
        "domain": "domain_name",
        "dataset_id": "dataset_identifier",
        "measure": "primary_metric_to_track",
        "aggregation": "SUM|AVG|COUNT|etc",
        "resolution": "Daily|Weekly|Monthly",
        "filters": [{{
            "column": "filter_column",
            "operator": "equals|contains|greater_than|etc",
            "value": "filter_value"
        }}],
        "drilldown_dimensions": ["dimension1", "dimension2"]
    }},
    "conditions": [
        {{
            "condition_type": "intelligent_arima|threshold_value|threshold_percent_change|threshold_change",
            "threshold_type": "based_on_value|based_on_change|based_on_percent_change",
            "operator": ">|<|>=|<=|=|!=",
            "value": 10.0
        }},
        {{
            "condition_type": "intelligent_arima|threshold_value|threshold_percent_change|threshold_change",
            "threshold_type": "based_on_value|based_on_change|based_on_percent_change",
            "operator": ">|<|>=|<=|=|!=",
            "value": 20.0
        }}
    ],
    "notification": {{
        "schedule_type": "daily|weekly|monthly|quarterly|yearly|custom|never",
        "metric_name": "descriptive_alert_name",
        "email_addresses": ["admin@company.com"],
        "subject": "Alert: [Metric Name] Threshold Exceeded",
        "email_message": "The tracked metric has exceeded the threshold...",
        "include_feed_report": true,
    }},
    "column_selection": {{
        "included": ["columns_for_insight_generation"],
        "excluded": ["date_columns", "id_columns"]
    }}
}}

Rules:
1. For percentage metrics like completion rates, use threshold_percent_change or threshold_value
2. For operational metrics, use Daily resolution and daily schedule_type
3. For strategic metrics, use Weekly/Monthly resolution with weekly/monthly schedule_type
4. Choose schedule_type based on business urgency: daily for critical ops, weekly for monitoring, monthly for strategic
5. Include relevant dimensions for breakdown analysis
6. Set appropriate thresholds based on business context AND sample data ranges
7. Use ARIMA for time-series patterns, thresholds for business rules
8. If sample data is available, use it to set realistic threshold values
9. Base notification messages on actual data patterns from the sample
10. Extract multiple conditions when the input describes multiple metrics or thresholds
11. Each condition should have its own threshold value and operator
12. Use only the exact enum values: "intelligent_arima", "threshold_value", "threshold_percent_change", "threshold_change" for condition_type
13. Use only the exact enum values: "daily", "weekly", "monthly", "quarterly", "yearly", "custom", "never" for schedule_type
14. Use only the exact enum values: ">", "<", ">=", "<=", "=", "!=" for operator
15. Use only the exact enum values: "Daily", "Weekly", "Monthly", "Quarterly", "Yearly" for resolution

IMPORTANT: If the input is ambiguous or unclear, return a clarification response instead of guessing:
- If you cannot determine the specific metric, threshold values, or operators
- If the business context is unclear
- If multiple interpretations are possible
- If critical information is missing

Return format for clarification:
{{
    "needs_clarification": true,
    "clarification_questions": [
        "What specific metric should be monitored?",
        "What threshold value should trigger the alert?",
        "What operator should be used (>, <, =, etc.)?"
    ],
    "ambiguous_elements": [
        "Unclear metric definition",
        "Missing threshold value"
    ],
    "suggested_improvements": [
        "Specify the exact column name for the metric",
        "Provide a specific threshold value",
        "Clarify the business context"
    ]
}}

Example for training completion: Alert when completion percentage < 90% AND expiry rate > 10%
This should generate two conditions: one for completion < 90% and another for expiry > 10%
""")
        
        chain = generation_prompt | self.alert_generator_llm | MarkdownJsonOutputParser()
        
        config_result = await chain.ainvoke({
            "tables": sql_analysis.tables,
            "metrics": sql_analysis.metrics,
            "dimensions": sql_analysis.dimensions,
            "filters": sql_analysis.filters,
            "aggregations": sql_analysis.aggregations,
            "alert_request": request.alert_request,
            "query": request.query,
            "domain_context": domain_context[:3],  # Top 3 relevant docs
            "sample_data_context": sample_data_context
        })
        
        # Debug logging: Log the raw JSON result from the LLM
        logger = logging.getLogger(__name__)
        logger.info(f"DEBUG: Raw JSON result from alert generator: {config_result}")
        logger.info(f"DEBUG: Type of config_result: {type(config_result)}")
        
        # Check if this is a clarification response
        if config_result.get("needs_clarification", False):
            logger.info("Alert generation requires clarification from user")
            return None  # Return None to indicate clarification needed
        
        # Fix enum values in the configuration
        config_result = self._fix_enum_values(config_result)
        
        # Debug logging: Log the result after enum fixing
        logger.info(f"DEBUG: JSON result after enum fixing: {config_result}")
        
        # Convert to Pydantic models
        metric = LexyFeedMetric(**config_result["metric"])
        
        # Handle multiple conditions
        conditions = []
        if "conditions" in config_result:
            for cond_data in config_result["conditions"]:
                conditions.append(LexyFeedCondition(**cond_data))
        elif "condition" in config_result:
            conditions.append(LexyFeedCondition(**config_result["condition"]))
        
        notification = LexyFeedNotification(**config_result["notification"])
        
        return LexyFeedConfiguration(
            metric=metric,
            conditions=conditions,
            notification=notification,
            column_selection=config_result["column_selection"]
        )
    
    async def _critique_alert_configuration(self, inputs: Dict) -> Dict[str, Any]:
        """Critique the generated Feed configuration"""
        
        request = inputs["request"]
        sql_analysis = inputs["sql_analysis"]
        feed_config = inputs["feed_configuration"]
        sample_data = request.sample_data
        
        # Prepare sample data context for critique
        sample_data_context = ""
        if sample_data and sample_data.get("data"):
            data = sample_data.get("data", [])
            columns = sample_data.get('columns', [])
            data_analysis = self._analyze_sample_data(data, columns)
            
            sample_data_context = f"""
Sample Data Context:
- Columns: {columns}
- Sample Rows: {data[:3]}
- Data Analysis: {data_analysis}
- Use this data to validate threshold values and condition appropriateness
"""

        critique_prompt = ChatPromptTemplate.from_template("""
Evaluate the generated Lexy Feed configuration for correctness and effectiveness:

Original Request: {alert_request}
SQL Analysis: {sql_analysis}
Generated Configuration: {feed_config}
{sample_data_context}

IMPORTANT: You must respond with ONLY valid JSON. Do not include any markdown formatting, comments, or explanatory text.

Evaluate on these criteria:
1. Does the metric selection match the SQL analysis?
2. Is the condition type appropriate for the alert request?
3. Are the threshold values reasonable based on the sample data and business context?
4. Does the resolution (Daily/Weekly/Monthly) fit the use case?
5. Are the drilldown dimensions relevant?
6. Is the notification schedule appropriate?
7. Is the original request clear and unambiguous?
8. Do the threshold values make sense given the actual data ranges?

If the original request is ambiguous or unclear, return a clarification response instead of evaluating the configuration.

Return JSON evaluation:
{{
    "is_valid": true,
    "confidence_score": 0.8,
    "critique_notes": ["specific issues found"],
    "suggestions": ["specific improvements"],
    "metric_appropriateness": 0.9,
    "condition_appropriateness": 0.8,
    "notification_appropriateness": 0.7,
    "needs_clarification": false,
    "clarification_questions": [],
    "ambiguous_elements": [],
    "suggested_improvements": []
}}

If clarification is needed, set "is_valid": false, "needs_clarification": true, and provide specific questions and ambiguous elements.
""")
        
        chain = critique_prompt | self.critic_llm | MarkdownJsonOutputParser()
        
        critique_result = await chain.ainvoke({
            "alert_request": request.alert_request,
            "sql_analysis": sql_analysis.dict(),
            "feed_config": feed_config.dict(),
            "sample_data_context": sample_data_context
        })
        
        # Debug logging: Log the critique result
        logger = logging.getLogger(__name__)
        logger.info(f"DEBUG: Critique result: {critique_result}")
        
        return critique_result
    
    async def _refine_alert_configuration(self, inputs: Dict) -> SQLAlertResult:
        """Refine the alert configuration based on critique"""
        
        request = inputs["request"]
        sql_analysis = inputs["sql_analysis"]
        feed_config = inputs["feed_configuration"]
        critique = inputs["critique"]
        
        # If configuration is good enough, return as-is
        if critique["is_valid"] and critique["confidence_score"] > 0.8:
            refined_config = feed_config
        else:
            # Refine based on critique feedback
            refinement_prompt = ChatPromptTemplate.from_template("""
Improve the Lexy Feed configuration based on critique feedback:

Original Configuration: {feed_config}
Critique Issues: {critique_notes}
Suggestions: {suggestions}
SQL Analysis: {sql_analysis}
Alert Request: {alert_request}

IMPORTANT: You must respond with ONLY valid JSON. Do not include any markdown formatting, comments, or explanatory text. The response must be parseable JSON.

Generate an improved configuration addressing all critique points.
Return the same JSON structure as before but with improvements:
{{
    "metric": {{
        "domain": "domain_name",
        "dataset_id": "dataset_identifier",
        "measure": "primary_metric_to_track",
        "aggregation": "SUM|AVG|COUNT|etc",
        "resolution": "Daily|Weekly|Monthly",
        "filters": [{{
            "column": "filter_column",
            "operator": "equals|contains|greater_than|etc",
            "value": "filter_value"
        }}],
        "drilldown_dimensions": ["dimension1", "dimension2"]
    }},
    "conditions": [
        {{
            "condition_type": "intelligent_arima|threshold_value|threshold_percent_change|threshold_change",
            "threshold_type": "based_on_value|based_on_change|based_on_percent_change",
            "operator": ">|<|>=|<=|=|!=",
            "value": 10.0
        }},
        {{
            "condition_type": "intelligent_arima|threshold_value|threshold_percent_change|threshold_change",
            "threshold_type": "based_on_value|based_on_change|based_on_percent_change",
            "operator": ">|<|>=|<=|=|!=",
            "value": 20.0
        }}
    ],
    "notification": {{
        "schedule_type": "daily|weekly|monthly|quarterly|yearly|custom|never",
        "metric_name": "descriptive_alert_name",
        "email_addresses": ["admin@company.com"],
        "subject": "Alert: [Metric Name] Threshold Exceeded",
        "email_message": "The tracked metric has exceeded the threshold...",
        "include_feed_report": true,
    }},
    "column_selection": {{
        "included": ["columns_for_insight_generation"],
        "excluded": ["date_columns", "id_columns"]
    }}
}}
""")
            
            chain = refinement_prompt | self.refiner_llm | MarkdownJsonOutputParser()
            
            refined_result = await chain.ainvoke({
                "feed_config": feed_config.dict(),
                "critique_notes": critique["critique_notes"],
                "suggestions": critique["suggestions"],
                "sql_analysis": sql_analysis.dict(),
                "alert_request": request.alert_request
            })
            
            # Debug logging: Log the refinement result
            logger = logging.getLogger(__name__)
            logger.info(f"DEBUG: Refinement result: {refined_result}")
            
            # Fix enum values in the refined configuration
            refined_result = self._fix_enum_values(refined_result)
            
            # Convert back to Pydantic models
            metric = LexyFeedMetric(**refined_result["metric"])
            condition = LexyFeedCondition(**refined_result["condition"])
            notification = LexyFeedNotification(**refined_result["notification"])
            
            refined_config = LexyFeedConfiguration(
                metric=metric,
                condition=condition,
                notification=notification,
                column_selection=refined_result["column_selection"]
            )
        
        return SQLAlertResult(
            feed_configuration=refined_config,
            sql_analysis=sql_analysis,
            confidence_score=critique["confidence_score"],
            critique_notes=critique["critique_notes"],
            suggestions=critique["suggestions"]
        )
    
    async def generate_alert(self, request: SQLAlertRequest) -> SQLAlertResult:
        """Main method to generate Lexy Feed alert from SQL + natural language"""
        
        # Debug logging: Log the input request
        logger = logging.getLogger(__name__)
        logger.info(f"DEBUG: generate_alert called with request: {request}")
        
        # Store session if provided
        if request.session_id:
            if request.session_id not in self.sessions:
                self.sessions[request.session_id] = {"history": []}
        
        # Run the Self-RAG pipeline
        result = await self.pipeline.ainvoke({"request": request})
        
        # Debug logging: Log the pipeline result
        logger.info(f"DEBUG: Pipeline result: {result}")
        logger.info(f"DEBUG: Pipeline result type: {type(result)}")
        
        # Check if the result indicates clarification is needed
        if hasattr(result, 'feed_configuration') and result.feed_configuration is None:
            # This indicates clarification is needed
            logger.info("Alert generation requires clarification from user")
            return result
        
        return result
    
    def _analyze_sample_data(self, data: List[Dict], columns: List[str]) -> str:
        """Analyze sample data to provide insights for alert generation"""
        if not data or not columns:
            return "No data available for analysis"
        
        analysis = []
        
        # Analyze each column
        for column in columns:
            values = [row.get(column) for row in data if row.get(column) is not None]
            if not values:
                continue
                
            # Try to determine data type and patterns
            try:
                # Check if numeric
                numeric_values = []
                for val in values:
                    try:
                        numeric_values.append(float(val))
                    except (ValueError, TypeError):
                        break
                
                if numeric_values:
                    min_val = min(numeric_values)
                    max_val = max(numeric_values)
                    avg_val = sum(numeric_values) / len(numeric_values)
                    
                    analysis.append(f"{column}: numeric (min={min_val:.2f}, max={max_val:.2f}, avg={avg_val:.2f})")
                else:
                    # String/categorical analysis
                    unique_values = list(set(str(v) for v in values))
                    if len(unique_values) <= 5:
                        analysis.append(f"{column}: categorical ({unique_values})")
                    else:
                        analysis.append(f"{column}: text ({len(unique_values)} unique values)")
                        
            except Exception:
                analysis.append(f"{column}: unknown type")
        
        return "; ".join(analysis) if analysis else "Unable to analyze data"

    def create_lexy_api_payload(self, result: SQLAlertResult) -> Dict[str, Any]:
        """Convert result to Lexy API payload format"""
        
        config = result.feed_configuration
        
        return {
            "feed": {
                "metric": {
                    "domain": config.metric.domain,
                    "datasetId": config.metric.dataset_id,
                    "measure": config.metric.measure,
                    "aggregation": config.metric.aggregation,
                    "resolution": config.metric.resolution,
                    "filters": config.metric.filters,
                    "drilldownDimensions": config.metric.drilldown_dimensions
                },
                "conditions": [
                    {
                        "type": cond.condition_type.value,
                        "thresholdType": cond.threshold_type,
                        "operator": cond.operator.value if cond.operator else None,
                        "value": cond.value
                    } for cond in config.conditions
                ],
                "notification": {
                    "scheduleType": config.notification.schedule_type.value,
                    "metricName": config.notification.metric_name,
                    "emailAddresses": config.notification.email_addresses,
                    "subject": config.notification.subject,
                    "emailMessage": config.notification.email_message,
                    "includeFeedReport": config.notification.include_feed_report,
                    "customSchedule": config.notification.custom_schedule
                },
                "columnSelection": {
                    "included": config.column_selection["included"],
                    "excluded": config.column_selection["excluded"]
                }
            },
            "confidence": result.confidence_score,
            "sqlAnalysis": result.sql_analysis.dict()
        }

# Specialized handlers for different alert patterns
class AlertPatternHandlers:
    """Specialized handlers for common alert patterns"""
    
    @staticmethod
    def training_completion_handler(sql_analysis: SQLAnalysis, alert_request: str) -> Dict[str, Any]:
        """Specialized handler for training completion alerts"""
        
        # Detect training-related patterns
        training_keywords = ["training", "completion", "assigned", "expired", "transcript"]
        is_training_related = any(keyword in alert_request.lower() or 
                                keyword in str(sql_analysis.metrics).lower() 
                                for keyword in training_keywords)
        
        if not is_training_related:
            return {}
        
        # Training-specific configuration
        return {
            "metric": {
                "domain": "training",
                "dataset_id": "training_dataset",
                "measure": "completion_percentage",
                "aggregation": "AVG",
                "resolution": "Daily",
                "filters": [],
                "drilldown_dimensions": ["training_type", "department"]
            },
            "condition": {
                "condition_type": "threshold_value",
                "threshold_type": "based_on_value",
                "operator": "<",
                "value": 90.0  # Alert when completion < 90%
            },
            "notification": {
                "schedule_type": "daily",
                "metric_name": "Training Completion Rate Alert",
                "subject": "Training Completion Below Threshold"
            }
        }
    
    @staticmethod
    def percentage_anomaly_handler(sql_analysis: SQLAnalysis, alert_request: str) -> Dict[str, Any]:
        """Handler for percentage-based anomaly detection"""
        
        percentage_metrics = [m for m in sql_analysis.metrics if "percentage" in m.lower() or "%" in m]
        
        if not percentage_metrics:
            return {}
        
        return {
            "condition": {
                "condition_type": "intelligent_arima",
                "threshold_type": None,
                "operator": None,
                "value": None
            },
            "notification": {
                "schedule_type": "daily",
                "metric_name": f"{percentage_metrics[0]} Anomaly Detection"
            }
        }



# Usage example and testing
async def example_usage():
    """Example usage of the SQL-to-Alert Agent"""
    
    # Method 1: Create LLM instances manually
    sql_parser_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.0)
    alert_generator_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)
    critic_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.0)
    refiner_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)
    
    # Method 2: Create from external settings (recommended)
    # settings = {
    #     "model_name": "gemini-2.0-flash",
    #     "sql_parser_temp": 0.0,
    #     "alert_generator_temp": 0.1,
    #     "critic_temp": 0.0,
    #     "refiner_temp": 0.2
    # }
    # sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm = create_llm_instances_from_settings(settings)
    
    # Initialize agent with LLM instances
    agent = SQLToAlertAgent(
        sql_parser_llm=sql_parser_llm,
        alert_generator_llm=alert_generator_llm,
        critic_llm=critic_llm,
        refiner_llm=refiner_llm
    )
    
    # Example request based on the provided training data
    request = SQLAlertRequest(
        sql="""SELECT tr.training_type AS "Training Type", 
               COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) AS "Assigned Count", 
               COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) AS "Completed Count", 
               COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) AS "Expired Count", 
               (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Assigned Percentage", 
               (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Completed Percentage", 
               (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Expired Percentage" 
               FROM csod_training_records AS tr GROUP BY tr.training_type""",
        query="What are the percentages of training activities by ActivityType and show their Training Statuses (Assigned, Completed, Expired)",
        project_id="cornerstone",
        data_description="Training completion tracking data",
        alert_request="Alert me for the groups that have percentage of activities not completed greater than 10%",
        session_id="training_alert_session"
    )
    
    try:
        result = await agent.generate_alert(request)
        
        print("Generated Alert Configuration:")
        print(f"Metric: {result.feed_configuration.metric.measure}")
        print(f"Conditions: {len(result.feed_configuration.conditions)} condition(s)")
        for i, cond in enumerate(result.feed_configuration.conditions):
            print(f"  Condition {i+1}: {cond.condition_type} {cond.operator} {cond.value}")
        print(f"Confidence: {result.confidence_score:.2f}")
        
        # Convert to Lexy API format
        api_payload = agent.create_lexy_api_payload(result)
        print(f"\nLexy API Payload:")
        print(json.dumps(api_payload, indent=2))
        
        return result
        
    except Exception as e:
        print(f"Error generating alert: {e}")
        return None

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())