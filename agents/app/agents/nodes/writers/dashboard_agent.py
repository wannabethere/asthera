import logging
import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from datetime import datetime

from langchain_core.tools import Tool
# Use centralized agent creation utility (imports AgentExecutor from there)
from app.agents.utils.agent_utils import create_agent_only, AgentExecutor
# Import prompts using modern LangChain paths
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder

# Import ConversationBufferWindowMemory (optional - will run without memory if not available)
try:
    from langchain.memory import ConversationBufferWindowMemory
except ImportError:
    try:
        from langchain_core.memory import ConversationBufferWindowMemory
    except ImportError:
        ConversationBufferWindowMemory = None

# Import BaseTool using modern LangChain paths
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langfuse.decorators import observe

from app.core.provider import DocumentStoreProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from .dashboard_models import DashboardConfiguration, ControlFilter, FilterType, FilterOperator, ConditionalFormat

logger = logging.getLogger("lexy-ai-service")


class ConditionalFormattingRetriever:
    """Retriever for historical conditional formatting configurations"""
    
    def __init__(self, retrieval_helper: RetrievalHelper):
        self.retrieval_helper = retrieval_helper
    
    async def retrieve_similar_configurations(
        self, 
        query: str, 
        project_id: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve similar historical configurations"""
        try:
            # Search for similar conditional formatting queries
            results = await self.retrieval_helper.search(
                query=query,
                collection_name="conditional_formatting_history",
                project_id=project_id,
                top_k=k
            )
            return results
        except Exception as e:
            logger.error(f"Error retrieving similar configurations: {e}")
            return []
    
    async def retrieve_filter_examples(
        self, 
        filter_type: str,
        project_id: str,
        k: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve examples of specific filter types"""
        try:
            query = f"filter type {filter_type} examples"
            results = await self.retrieval_helper.search(
                query=query,
                collection_name="filter_examples",
                project_id=project_id,
                top_k=k
            )
            return results
        except Exception as e:
            logger.error(f"Error retrieving filter examples: {e}")
            return []


class ConditionalFormattingAgent:
    """LangChain agent for conditional formatting translation"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retriever: ConditionalFormattingRetriever,
        document_store_provider: DocumentStoreProvider
    ):
        self.llm = llm
        self.retriever = retriever
        self.document_store_provider = document_store_provider
        
        # Initialize memory if available, otherwise use None
        if ConversationBufferWindowMemory is not None:
            self.memory = ConversationBufferWindowMemory(
                memory_key="chat_history",
                return_messages=True,
                k=10
            )
        else:
            logger.warning("ConversationBufferWindowMemory not available, running without memory")
            self.memory = None
        
        # Initialize tools and agent
        self.tools = self._create_tools()
        self.agent = self._create_agent()
        
        if self.agent is None:
            raise RuntimeError("Failed to create agent. Cannot initialize ConditionalFormattingAgent.")
        
        # Build AgentExecutor kwargs, only include memory if available
        executor_kwargs = {
            "agent": self.agent,
            "tools": self.tools,
            "verbose": True,
            "max_iterations": 3,  # Reduced to prevent long execution times
            "handle_parsing_errors": True,
            "return_intermediate_steps": False  # Don't return intermediate steps to reduce overhead
        }
        if self.memory is not None:
            executor_kwargs["memory"] = self.memory
            
        self.agent_executor = AgentExecutor(**executor_kwargs)
    
    def _create_tools(self) -> List[BaseTool]:
        """Create tools for the agent"""
        
        class FilterExamplesTool(BaseTool):
            name: str = "get_filter_examples"
            description: str = "Get examples of conditional filters for specific types"
            
            def __init__(self, retriever):
                super().__init__()
                self._retriever = retriever
            
            def _run(self, filter_type: str, project_id: str) -> str:
                try:
                    examples = asyncio.run(
                        self._retriever.retrieve_filter_examples(filter_type, project_id)
                    )
                    return json.dumps(examples, indent=2)
                except Exception as e:
                    return f"Error retrieving examples: {e}"
            
            async def _arun(self, filter_type: str, project_id: str) -> str:
                try:
                    examples = await self._retriever.retrieve_filter_examples(filter_type, project_id)
                    return json.dumps(examples, indent=2)
                except Exception as e:
                    return f"Error retrieving examples: {e}"
        
        class SimilarConfigurationsTool(BaseTool):
            name: str = "get_similar_configurations"
            description: str = "Get similar historical conditional formatting configurations"
            
            def __init__(self, retriever):
                super().__init__()
                self._retriever = retriever
            
            def _run(self, query: str, project_id: str) -> str:
                try:
                    configurations = asyncio.run(
                        self._retriever.retrieve_similar_configurations(query, project_id)
                    )
                    return json.dumps(configurations, indent=2)
                except Exception as e:
                    return f"Error retrieving configurations: {e}"
            
            async def _arun(self, query: str, project_id: str) -> str:
                try:
                    configurations = await self._retriever.retrieve_similar_configurations(query, project_id)
                    return json.dumps(configurations, indent=2)
                except Exception as e:
                    return f"Error retrieving configurations: {e}"
        
        class ValidateConfigurationTool(BaseTool):
            name: str = "validate_configuration"
            description: str = "Validate a conditional formatting configuration"
            
            def _run(self, config_json: str) -> str:
                try:
                    config = json.loads(config_json)
                    # Basic validation logic
                    required_fields = ["dashboard_id", "filters", "conditional_formats"]
                    for field in required_fields:
                        if field not in config:
                            return f"Missing required field: {field}"
                    
                    # Validate filters - different filter types have different required fields
                    for filter_obj in config.get("filters", []):
                        filter_type = filter_obj.get("filter_type", "")
                        
                        if filter_type == "time_filter":
                            # Time filters require start_date/end_date or period, not column_name/operator
                            if not any(key in filter_obj for key in ["start_date", "end_date", "period"]):
                                return "Invalid time_filter configuration: missing start_date, end_date, or period"
                        elif filter_type == "column_filter":
                            # Column filters require column_name and operator
                            if "column_name" not in filter_obj or "operator" not in filter_obj:
                                return "Invalid column_filter configuration: missing column_name or operator"
                        elif filter_type == "conditional_format":
                            # Conditional format filters require column_name and operator
                            if "column_name" not in filter_obj or "operator" not in filter_obj:
                                return "Invalid conditional_format configuration: missing column_name or operator"
                        else:
                            # For other filter types, check for basic structure
                            if "filter_id" not in filter_obj or "filter_type" not in filter_obj:
                                return f"Invalid {filter_type} configuration: missing filter_id or filter_type"
                    
                    # Validate conditional_formats
                    for format_obj in config.get("conditional_formats", []):
                        required_format_fields = ["format_id", "chart_id", "condition", "formatting_rules"]
                        for field in required_format_fields:
                            if field not in format_obj:
                                return f"Invalid conditional_format: missing {field}"
                        
                        # Validate condition within conditional_format
                        condition = format_obj.get("condition", {})
                        if not isinstance(condition, dict):
                            return "Invalid conditional_format: condition must be an object"
                        if "column_name" not in condition or "operator" not in condition:
                            return "Invalid conditional_format condition: missing column_name or operator"
                    
                    return "Configuration is valid"
                except json.JSONDecodeError as e:
                    return f"Validation error: Invalid JSON - {e}"
                except Exception as e:
                    return f"Validation error: {e}"
            
            async def _arun(self, config_json: str) -> str:
                # Same logic as _run since validation is synchronous
                return self._run(config_json)
        
        return [FilterExamplesTool(self.retriever), SimilarConfigurationsTool(self.retriever), ValidateConfigurationTool()]
    
    def _create_agent(self):
        """Create the LangChain agent using centralized utility"""
        
        # Use centralized agent creation utility with custom prompt for create_tool_calling_agent fallback
        system_prompt = """You are an expert in translating natural language queries into dashboard conditional formatting configurations.

Your task is to:
1. Understand natural language queries about conditional formatting and control filters
2. Translate them into structured configuration objects
3. Use historical examples and similar configurations for reference (but DO NOT return the examples directly - use them as inspiration)
4. Generate appropriate SQL expansion and chart adjustment configurations
5. Self-evaluate your configurations for accuracy and completeness

IMPORTANT: When you retrieve examples using tools, use them as reference only. DO NOT return the example data directly. You must generate a NEW configuration based on the user's query, using the examples as guidance.

Key concepts:
- Control Filters: Filter data based on conditions (equals, greater than, contains, etc.)
- Conditional Formatting: Apply visual formatting based on data conditions
- Time Filters: Apply time-based filtering (date ranges, periods, etc.)
- SQL Expansion: Modify SQL queries to include filter conditions
- Chart Adjustment: Modify chart appearance and formatting

Available filter operators: equals, not_equals, greater_than, less_than, greater_equal, less_equal, contains, not_contains, starts_with, ends_with, in, not_in, between, is_null, is_not_null, regex

Available filter types: column_filter, time_filter, conditional_format, aggregation_filter, custom_filter

Always use the available tools to:
- Get examples of similar filter types (for reference only - do not return them)
- Retrieve historical configurations (for reference only - do not return them)
- Validate your generated configurations

You MUST generate a NEW configuration in this format (do not return example data):
```json
{{
    "dashboard_id": "dashboard_123",
    "filters": [
        {{
            "filter_id": "filter_1",
            "filter_type": "column_filter",
            "column_name": "status",
            "operator": "equals",
            "value": "active",
            "description": "Filter for active records"
        }}
    ],
    "conditional_formats": [
        {{
            "format_id": "format_1",
            "chart_id": "chart_1",
            "condition": {{
                "filter_id": "condition_1",
                "filter_type": "conditional_format",
                "column_name": "sales",
                "operator": "greater_than",
                "value": 1000
            }},
            "formatting_rules": {{
                "color": "green",
                "font_weight": "bold"
            }},
            "description": "Highlight high sales"
        }}
    ],
    "time_filters": {{
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "period": "last_30_days"
    }}
}}
```

Remember to:
1. Self-evaluate your configurations and use tools for validation
2. Generate a NEW configuration based on the user's query
3. DO NOT return the example data from tools - use it only as reference
4. Always output the configuration in the JSON format shown above, wrapped in ```json code blocks"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Use centralized utility with custom prompt for fallback
        return create_agent_only(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt,
            use_react_agent=True  # Try create_react_agent first, fallback to create_tool_calling_agent with custom prompt
        )
    
    @observe(name="ConditionalFormattingAgent")
    async def process_conditional_formatting_request(
        self,
        query: str,
        dashboard_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process conditional formatting request and return result compatible with pipeline expectations"""
        try:
            # Process the query using the existing method
            dashboard_config = await self.process_query(
                query=query,
                dashboard_context=dashboard_context,
                project_id=project_id,
                additional_context=additional_context
            )
            
            # Convert to the format expected by the pipeline
            chart_configurations = dashboard_config.get_chart_configurations()
            
            # Prepare the result structure
            result = {
                "success": True,
                "configuration": dashboard_config,
                "chart_configurations": chart_configurations,
                "metadata": {
                    "project_id": project_id,
                    "query": query,
                    "dashboard_context": dashboard_context,
                    "additional_context": additional_context,
                    "time_filters": time_filters,
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            return result
            
        except json.JSONDecodeError as json_error:
            logger.error(f"JSON parsing error in conditional formatting request: {json_error}")
            logger.error(f"JSON error details: line {json_error.lineno}, column {json_error.colno}, position {json_error.pos}")
            return {
                "success": False,
                "error": f"Invalid JSON configuration: {str(json_error)}",
                "chart_configurations": {},
                "metadata": {
                    "project_id": project_id,
                    "query": query,
                    "error": str(json_error),
                    "error_type": "json_parse_error"
                }
            }
        except Exception as e:
            logger.error(f"Error processing conditional formatting request: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "chart_configurations": {},
                "metadata": {
                    "project_id": project_id,
                    "query": query,
                    "error": str(e)
                }
            }

    @observe(name="ConditionalFormattingAgent")
    async def process_query(
        self,
        query: str,
        dashboard_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> DashboardConfiguration:
        """Process natural language query and generate configuration"""
        try:
            # Prepare input with context
            input_data = {
                "input": f"""
Natural Language Query: {query}

Dashboard Context: {json.dumps(dashboard_context, indent=2)}

Project ID: {project_id}

Additional Context: {json.dumps(additional_context or {}, indent=2)}

Please translate this natural language query into a conditional formatting configuration.
Use the available tools to get examples and validate your configuration.
""",
                "chat_history": self.memory.chat_memory.messages
            }
            
            # Run the agent with timeout to prevent hanging
            import asyncio
            logger.info("Starting conditional formatting agent execution...")
            start_time = asyncio.get_event_loop().time()
            
            try:
                result = await asyncio.wait_for(
                    self.agent_executor.ainvoke(input_data),
                    timeout=90.0  # 90 second timeout for agent execution
                )
                end_time = asyncio.get_event_loop().time()
                execution_time = end_time - start_time
                logger.info(f"Agent executor completed in {execution_time:.2f} seconds")
            except asyncio.TimeoutError:
                end_time = asyncio.get_event_loop().time()
                execution_time = end_time - start_time
                logger.error(f"Agent executor timed out after {execution_time:.2f} seconds (timeout: 90s)")
                raise ValueError("Conditional formatting agent execution timed out. The request may be too complex or the agent is stuck in a loop. Please try simplifying your query.")
            except Exception as e:
                end_time = asyncio.get_event_loop().time()
                execution_time = end_time - start_time
                logger.error(f"Agent executor error after {execution_time:.2f} seconds: {e}")
                raise
            
            # Parse the result
            configuration_json = self._extract_configuration_from_result(result["output"])
            
            if configuration_json:
                # Clean and parse JSON configuration
                try:
                    # Try parsing with standard json module
                    config_data = json.loads(configuration_json)
                    logger.info("Successfully parsed JSON configuration")
                except json.JSONDecodeError as json_error:
                    logger.warning(f"Initial JSON parse failed, attempting to clean JSON: {json_error}")
                    logger.warning(f"JSON error at line {json_error.lineno}, column {json_error.colno}, position {json_error.pos}")
                    logger.debug(f"Problematic JSON substring: {configuration_json[max(0, json_error.pos-50):json_error.pos+50]}")
                    
                    # Attempt to clean the JSON string
                    cleaned_json = self._clean_json_string(configuration_json)
                    logger.debug(f"Cleaned JSON length: {len(cleaned_json)} (original: {len(configuration_json)})")
                    
                    try:
                        config_data = json.loads(cleaned_json)
                        logger.info("Successfully parsed JSON after cleaning")
                    except json.JSONDecodeError as cleaned_error:
                        logger.error(f"Failed to parse JSON even after cleaning: {cleaned_error}")
                        logger.error(f"Cleaned JSON error at line {cleaned_error.lineno}, column {cleaned_error.colno}, position {cleaned_error.pos}")
                        logger.error(f"Original JSON string (first 500 chars): {configuration_json[:500]}")
                        logger.error(f"Cleaned JSON string (first 500 chars): {cleaned_json[:500]}")
                        raise ValueError(f"Invalid JSON configuration: {str(cleaned_error)}. Original error: {str(json_error)}")
                
                # Convert filters - separate time filters from other filters
                filters = []
                time_filters_dict = {}
                
                for filter_data in config_data.get("filters", []):
                    filter_type = filter_data.get("filter_type", "")
                    
                    if filter_type == "time_filter":
                        # Time filters go into time_filters dict, not filters list
                        time_filters_dict.update({
                            "start_date": filter_data.get("start_date"),
                            "end_date": filter_data.get("end_date"),
                            "period": filter_data.get("period"),
                            "description": filter_data.get("description")
                        })
                        # Remove None values
                        time_filters_dict = {k: v for k, v in time_filters_dict.items() if v is not None}
                    else:
                        # Other filter types require column_name and operator
                        if "column_name" not in filter_data or "operator" not in filter_data:
                            logger.warning(f"Skipping filter {filter_data.get('filter_id')} - missing column_name or operator")
                            continue
                        
                        filter_obj = ControlFilter(
                            filter_id=filter_data["filter_id"],
                            filter_type=FilterType(filter_type),
                            column_name=filter_data["column_name"],
                            operator=FilterOperator(filter_data["operator"]),
                            value=filter_data.get("value"),
                            condition=filter_data.get("condition"),
                            description=filter_data.get("description")
                        )
                        filters.append(filter_obj)
                
                # Convert conditional formats
                conditional_formats = []
                for format_data in config_data.get("conditional_formats", []):
                    condition_data = format_data["condition"]
                    condition = ControlFilter(
                        filter_id=condition_data["filter_id"],
                        filter_type=FilterType(condition_data["filter_type"]),
                        column_name=condition_data["column_name"],
                        operator=FilterOperator(condition_data["operator"]),
                        value=condition_data["value"],
                        condition=condition_data.get("condition"),
                        description=condition_data.get("description")
                    )
                    
                    conditional_format = ConditionalFormat(
                        format_id=format_data["format_id"],
                        chart_id=format_data["chart_id"],
                        condition=condition,
                        formatting_rules=format_data["formatting_rules"],
                        description=format_data.get("description")
                    )
                    conditional_formats.append(conditional_format)
                
                # Merge time_filters from filters list and time_filters field
                final_time_filters = config_data.get("time_filters", {})
                if time_filters_dict:
                    final_time_filters.update(time_filters_dict)
                
                return DashboardConfiguration(
                    dashboard_id=config_data["dashboard_id"],
                    filters=filters,
                    conditional_formats=conditional_formats,
                    time_filters=final_time_filters if final_time_filters else None,
                    global_context=additional_context,
                    actions=config_data.get("actions")
                )
            else:
                raise ValueError("Failed to extract valid configuration from agent response")
        
        except Exception as e:
            logger.error(f"Error processing conditional formatting query: {e}")
            raise
    
    def _extract_configuration_from_result(self, result: str) -> Optional[str]:
        """Extract JSON configuration from agent result, handling tool invocations and various formats"""
        try:
            import re
            import json as json_module
            
            # First, try to find JSON in code blocks (most reliable - agent's final output)
            json_pattern = r'```json\s*(.*?)\s*```'
            match = re.search(json_pattern, result, re.DOTALL)
            
            if match:
                json_str = match.group(1).strip()
                # Try to validate it's valid JSON by parsing
                try:
                    parsed = json_module.loads(json_str)
                    if isinstance(parsed, dict) and "dashboard_id" in parsed:
                        logger.info("Extracted JSON from code block")
                        return json_str
                except json_module.JSONDecodeError as e:
                    # If parsing fails, try to extract just the JSON object
                    logger.warning(f"JSON found in code block but failed to parse: {e}, trying to extract valid JSON")
                    # Try to find the first complete JSON object
                    start_idx = json_str.find('{')
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(json_str)):
                            if json_str[i] == '{':
                                brace_count += 1
                            elif json_str[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        
                        if end_idx > start_idx:
                            extracted_json = json_str[start_idx:end_idx].strip()
                            try:
                                parsed = json_module.loads(extracted_json)
                                if isinstance(parsed, dict) and "dashboard_id" in parsed:
                                    logger.info("Extracted JSON from code block after cleaning")
                                    return extracted_json
                            except json_module.JSONDecodeError:
                                pass
                    # If still fails, continue to try other extraction methods
                    pass
            
            # Third, try to find JSON objects directly (handle cases without code blocks)
            # Use balanced brace matching to find complete JSON objects
            start_idx = result.find('{')
            if start_idx != -1:
                brace_count = 0
                end_idx = start_idx
                in_string = False
                escape_next = False
                
                for i in range(start_idx, len(result)):
                    char = result[i]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\':
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                
                if end_idx > start_idx:
                    json_str = result[start_idx:end_idx].strip()
                    try:
                        parsed = json_module.loads(json_str)
                        if isinstance(parsed, dict) and "dashboard_id" in parsed:
                            logger.info("Extracted JSON using balanced brace matching")
                            return json_str
                    except json_module.JSONDecodeError as e:
                        # Try cleaning the JSON
                        cleaned_json = self._clean_json_string(json_str)
                        try:
                            parsed = json_module.loads(cleaned_json)
                            if isinstance(parsed, dict) and "dashboard_id" in parsed:
                                logger.info("Extracted JSON after cleaning")
                                return cleaned_json
                        except json_module.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON even after cleaning: {e}")
            
            # Fourth, try to find JSON after "Finished chain" or similar markers
            # Sometimes the agent output has the JSON after tool invocations
            finished_markers = [
                "Configuration is valid",
                "Here is the final conditional formatting configuration",
                "Here is the final",
                "Finished chain",
                "> Finished"
            ]
            for marker in finished_markers:
                marker_idx = result.find(marker)
                if marker_idx != -1:
                    # Look for JSON after this marker (skip any text after the marker)
                    remaining = result[marker_idx + len(marker):]
                    # Skip any text until we find a JSON object start
                    start_idx = remaining.find('{')
                    # Also try to find JSON in code blocks after the marker
                    code_block_match = re.search(r'```json\s*(.*?)\s*```', remaining, re.DOTALL)
                    if code_block_match:
                        json_str = code_block_match.group(1).strip()
                        try:
                            parsed = json_module.loads(json_str)
                            if isinstance(parsed, dict) and "dashboard_id" in parsed:
                                logger.info(f"Extracted JSON from code block after marker '{marker}'")
                                return json_str
                        except json_module.JSONDecodeError:
                            pass
                    
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = start_idx
                        in_string = False
                        escape_next = False
                        
                        for i in range(start_idx, len(remaining)):
                            char = remaining[i]
                            
                            if escape_next:
                                escape_next = False
                                continue
                            
                            if char == '\\':
                                escape_next = True
                                continue
                            
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_idx = i + 1
                                        break
                        
                        if end_idx > start_idx:
                            json_str = remaining[start_idx:end_idx].strip()
                            try:
                                parsed = json_module.loads(json_str)
                                if isinstance(parsed, dict) and "dashboard_id" in parsed:
                                    logger.info(f"Extracted JSON after marker '{marker}'")
                                    return json_str
                            except json_module.JSONDecodeError:
                                # Try cleaning
                                cleaned_json = self._clean_json_string(json_str)
                                try:
                                    parsed = json_module.loads(cleaned_json)
                                    if isinstance(parsed, dict) and "dashboard_id" in parsed:
                                        logger.info(f"Extracted JSON after marker '{marker}' and cleaning")
                                        return cleaned_json
                                except json_module.JSONDecodeError:
                                    pass
            
            # Fifth, try to extract JSON from tool invocation results (fallback)
            # Look for patterns like: Invoking: `validate_configuration` with `{'config_json': '...'}`
            # Handle both single and double quotes, and escaped quotes
            tool_invocation_patterns = [
                r"config_json['\"]:\s*['\"](.*?)['\"]",  # Simple pattern
                r"config_json['\"]:\s*['\"]((?:[^'\"\\]|\\.)*)['\"]",  # Pattern with escaped quotes
                r"'config_json':\s*'((?:[^'\\]|\\.)*)'",  # Single quotes with escapes
                r'"config_json":\s*"((?:[^"\\]|\\.)*)"',  # Double quotes with escapes
            ]
            
            for pattern in tool_invocation_patterns:
                tool_match = re.search(pattern, result, re.DOTALL)
                if tool_match:
                    json_str = tool_match.group(1)
                    # Unescape the JSON string (handle escaped quotes and newlines)
                    json_str = json_str.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')
                    try:
                        parsed = json_module.loads(json_str)
                        if isinstance(parsed, dict) and "dashboard_id" in parsed:
                            logger.info("Extracted JSON from tool invocation")
                            return json_str
                    except json_module.JSONDecodeError as e:
                        # Try cleaning the JSON
                        cleaned_json = self._clean_json_string(json_str)
                        try:
                            parsed = json_module.loads(cleaned_json)
                            if isinstance(parsed, dict) and "dashboard_id" in parsed:
                                logger.info("Extracted JSON from tool invocation after cleaning")
                                return cleaned_json
                        except json_module.JSONDecodeError:
                            logger.debug(f"JSON from tool invocation failed to parse even after cleaning: {e}")
                            continue
            
            logger.warning("Could not extract valid JSON configuration from agent response")
            logger.warning(f"Full agent response (first 2000 chars): {result[:2000]}")
            logger.warning(f"Full agent response (last 1000 chars): {result[-1000:] if len(result) > 1000 else result}")
            
            # Try to detect if agent returned example data instead of configuration
            if '"instruction"' in result or '"instruction_id"' in result:
                logger.error("Agent appears to have returned example/instruction data instead of generating a configuration. This suggests the agent is confused about its task.")
            
            return None
        except Exception as e:
            logger.error(f"Error extracting configuration: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.debug(f"Response that caused error (first 1000 chars): {result[:1000] if result else 'None'}")
            return None
    
    def _clean_json_string(self, json_str: str) -> str:
        """Clean JSON string to fix common issues"""
        import re
        
        # Remove leading/trailing whitespace
        json_str = json_str.strip()
        
        # Remove JavaScript-style comments (// and /* */)
        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # Remove trailing commas before closing braces/brackets (more aggressive)
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix single quotes to double quotes - handle multiple patterns
        # Pattern 1: Property names with single quotes: 'key': value
        json_str = re.sub(r"'([^']+)'\s*:", r'"\1":', json_str)
        
        # Pattern 2: String values with single quotes: key: 'value'
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
        
        # Pattern 3: Fix array values with single quotes
        json_str = re.sub(r"\[\s*'([^']*)'\s*\]", r'["\1"]', json_str)
        json_str = re.sub(r",\s*'([^']*)'\s*", r', "\1"', json_str)
        
        # Pattern 4: Fix single quotes in nested objects within arrays or objects
        # Handle cases like: {'key': 'value'} -> {"key": "value"}
        json_str = re.sub(r"{\s*'([^']+)'\s*:\s*'([^']*)'\s*}", r'{"\1": "\2"}', json_str)
        
        # Remove any control characters that might cause issues (but keep newlines, tabs, returns)
        json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
        
        # Final cleanup: ensure proper spacing around colons and commas
        json_str = re.sub(r'\s*:\s*', ': ', json_str)
        json_str = re.sub(r'\s*,\s*', ', ', json_str)
        
        return json_str

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics for the conditional formatting agent"""
        return {
            "agent_type": "ConditionalFormattingAgent",
            "tools_count": len(self.tools),
            "memory_size": len(self.memory.chat_memory.messages) if self.memory.chat_memory else 0,
            "llm_provider": self.llm.__class__.__name__ if self.llm else "Unknown",
            "retriever_type": self.retriever.__class__.__name__ if self.retriever else "Unknown",
            "document_store_provider": self.document_store_provider.__class__.__name__ if self.document_store_provider else "Unknown"
        }
