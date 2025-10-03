import logging
import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from datetime import datetime

from langchain.agents import Tool, AgentExecutor, create_tool_calling_agent
from langchain.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferWindowMemory
from langchain.tools import BaseTool
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
        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=10
        )
        
        # Initialize tools and agent
        self.tools = self._create_tools()
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=5,
            early_stopping_method="generate"
        )
    
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
                    
                    # Validate filters
                    for filter_obj in config.get("filters", []):
                        if "column_name" not in filter_obj or "operator" not in filter_obj:
                            return "Invalid filter configuration"
                    
                    return "Configuration is valid"
                except Exception as e:
                    return f"Validation error: {e}"
            
            async def _arun(self, config_json: str) -> str:
                # Same logic as _run since validation is synchronous
                return self._run(config_json)
        
        return [FilterExamplesTool(self.retriever), SimilarConfigurationsTool(self.retriever), ValidateConfigurationTool()]
    
    def _create_agent(self):
        """Create the LangChain agent"""
        
        system_prompt = """You are an expert in translating natural language queries into dashboard conditional formatting configurations.

Your task is to:
1. Understand natural language queries about conditional formatting and control filters
2. Translate them into structured configuration objects
3. Use historical examples and similar configurations for reference
4. Generate appropriate SQL expansion and chart adjustment configurations
5. Self-evaluate your configurations for accuracy and completeness

Key concepts:
- Control Filters: Filter data based on conditions (equals, greater than, contains, etc.)
- Conditional Formatting: Apply visual formatting based on data conditions
- Time Filters: Apply time-based filtering (date ranges, periods, etc.)
- SQL Expansion: Modify SQL queries to include filter conditions
- Chart Adjustment: Modify chart appearance and formatting

Available filter operators: equals, not_equals, greater_than, less_than, greater_equal, less_equal, contains, not_contains, starts_with, ends_with, in, not_in, between, is_null, is_not_null, regex

Available filter types: column_filter, time_filter, conditional_format, aggregation_filter, custom_filter

Always use the available tools to:
- Get examples of similar filter types
- Retrieve historical configurations
- Validate your generated configurations

Generate configurations in this format:
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

Remember to self-evaluate your configurations and use tools for validation."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        return create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
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
            
        except Exception as e:
            logger.error(f"Error processing conditional formatting request: {e}")
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
            
            # Run the agent
            result = await self.agent_executor.ainvoke(input_data)
            
            # Parse the result
            configuration_json = self._extract_configuration_from_result(result["output"])
            
            if configuration_json:
                # Convert to DashboardConfiguration object
                config_data = json.loads(configuration_json)
                
                # Convert filters
                filters = []
                for filter_data in config_data.get("filters", []):
                    filter_obj = ControlFilter(
                        filter_id=filter_data["filter_id"],
                        filter_type=FilterType(filter_data["filter_type"]),
                        column_name=filter_data["column_name"],
                        operator=FilterOperator(filter_data["operator"]),
                        value=filter_data["value"],
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
                
                return DashboardConfiguration(
                    dashboard_id=config_data["dashboard_id"],
                    filters=filters,
                    conditional_formats=conditional_formats,
                    time_filters=config_data.get("time_filters"),
                    global_context=additional_context,
                    actions=config_data.get("actions")
                )
            else:
                raise ValueError("Failed to extract valid configuration from agent response")
        
        except Exception as e:
            logger.error(f"Error processing conditional formatting query: {e}")
            raise
    
    def _extract_configuration_from_result(self, result: str) -> Optional[str]:
        """Extract JSON configuration from agent result"""
        try:
            # Look for JSON in code blocks
            import re
            json_pattern = r'```json\s*(.*?)\s*```'
            match = re.search(json_pattern, result, re.DOTALL)
            
            if match:
                return match.group(1)
            
            # Look for JSON objects directly
            json_pattern = r'\{.*\}'
            match = re.search(json_pattern, result, re.DOTALL)
            
            if match:
                return match.group(0)
            
            return None
        except Exception as e:
            logger.error(f"Error extracting configuration: {e}")
            return None

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
