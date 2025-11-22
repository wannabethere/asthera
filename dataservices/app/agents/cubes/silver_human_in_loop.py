"""
Human-in-the-Loop Agents for Silver Table Generation Workflow

This module provides interactive agents that engage with users to:
1. Generate questions based on table metadata
2. Collect business goals and purposes
3. Identify analysis types and unique keys
4. Enrich with Wikipedia and domain knowledge
5. Establish data governance requirements

Integrates with:
- project_manager.py: For LLM definition generation
- schema_manager.py: For schema documentation
- semantics_description.py: For semantic analysis
- relationship_recommendation.py: For relationship suggestions
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from enum import Enum
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import asyncio
import re
import logging

logger = logging.getLogger("genieml-agents")


# ============================================================================
# LLM LOGGING HELPER
# ============================================================================

def log_llm_call(stage: str, messages: List, response: Any, max_response_length: int = 500):
    """
    Log LLM request and response for debugging.
    
    Args:
        stage: Name of the stage/operation (e.g., "Domain Enrichment", "Question Generation")
        messages: List of messages sent to LLM
        response: LLM response object
        max_response_length: Maximum length of response to log (truncate if longer)
    """
    # Extract prompt from messages
    system_msg = next((msg.content for msg in messages if isinstance(msg, SystemMessage)), None)
    user_msg = next((msg.content for msg in messages if isinstance(msg, HumanMessage)), None)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🤖 LLM CALL: {stage}")
    logger.info(f"{'='*80}")
    
    if system_msg:
        logger.debug(f"System Message: {system_msg[:200]}...")
    
    if user_msg:
        # Log first 300 chars of user message
        user_preview = user_msg[:300] + "..." if len(user_msg) > 300 else user_msg
        logger.info(f"User Prompt Preview: {user_preview}")
    
    # Log response
    if hasattr(response, 'content'):
        response_content = response.content
        if len(response_content) > max_response_length:
            logger.info(f"LLM Response ({len(response_content)} chars, truncated):\n{response_content[:max_response_length]}...")
            logger.debug(f"Full Response:\n{response_content}")
        else:
            logger.info(f"LLM Response ({len(response_content)} chars):\n{response_content}")
    else:
        logger.info(f"LLM Response: {response}")
    
    logger.info(f"{'='*80}\n")


def safe_llm_invoke(llm: ChatOpenAI, messages: List, stage: str, default_return: Any = None):
    """
    Safely invoke LLM with error handling for authentication and other errors.
    
    Args:
        llm: The LLM instance to use
        messages: List of messages to send
        stage: Stage name for logging
        default_return: Default value to return if LLM call fails
        
    Returns:
        LLM response or default_return if error occurs
    """
    try:
        response = llm.invoke(messages)
        log_llm_call(stage, messages, response)
        return response
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        logger.error(f"\n{'='*80}")
        logger.error(f"❌ LLM CALL FAILED: {stage}")
        logger.error(f"{'='*80}")
        logger.error(f"Error Type: {error_type}")
        logger.error(f"Error Message: {error_msg}")
        
        # Check for authentication errors
        if "401" in error_msg or "AuthenticationError" in error_type or "invalid_organization" in error_msg:
            logger.error(
                "\n⚠️  AUTHENTICATION ERROR DETECTED:\n"
                "The OpenAI API key may be:\n"
                "1. Invalid or expired\n"
                "2. Not have access to the required organization\n"
                "3. Tied to a different organization\n"
                "\nPlease check your OPENAI_API_KEY in settings.py or environment variables.\n"
                "You may need to:\n"
                "- Generate a new API key from https://platform.openai.com/api-keys\n"
                "- Ensure the key has access to the correct organization\n"
                "- Update the key in your settings or .env file\n"
            )
        
        logger.error(f"{'='*80}\n")
        
        if default_return is not None:
            logger.warning(f"Returning default value for {stage} due to LLM error")
            return default_return
        else:
            raise

# Import existing services
from app.agents.semantics_description import SemanticsDescription
from app.agents.schema_manager import LLMSchemaDocumentationGenerator, SchemaDocumentationUtils
from app.service.models import DomainContext, SchemaInput
from app.core.dependencies import get_llm

# Import cube generation models (using relative import to avoid circular dependency)
from .cube_generation_agent import (
    TableDDL,
    TableMetadataSummary,
    ColumnMetadata,
    AgentState,
    LODConfig,
    RelationshipMapping
)

# Import data mart planner
from .data_mart_planner_agent import DataMartPlannerAgent, DataMartPlan


# ============================================================================
# DATA MODELS
# ============================================================================

class AnalysisType(str, Enum):
    """Analysis type enumeration"""
    DESCRIPTIVE = "descriptive"  # What happened?
    DIAGNOSTIC = "diagnostic"  # Why did it happen?
    PREDICTIVE = "predictive"  # What will happen?
    PRESCRIPTIVE = "prescriptive"  # What should we do?
    EXPLORATORY = "exploratory"  # What patterns exist?
    COMPARATIVE = "comparative"  # How do things compare?
    TREND = "trend"  # How are things changing?
    SEGMENTATION = "segmentation"  # How to group data?
    COHORT = "cohort"  # How do groups behave over time?
    FUNNEL = "funnel"  # Where do users drop off?


class BusinessGoal(BaseModel):
    """Business goal definition"""
    goal_name: str
    description: str
    priority: str = "medium"  # high, medium, low
    kpis: List[str] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    stakeholders: List[str] = Field(default_factory=list)


class TableAnalysisConfig(BaseModel):
    """Configuration for table analysis collected from user"""
    table_name: str
    analysis_types: List[str] = Field(default_factory=list)
    unique_keys: List[str] = Field(default_factory=list)
    business_goals: List[BusinessGoal] = Field(default_factory=list)
    business_purpose: Optional[str] = None
    domain_knowledge: Dict[str, Any] = Field(default_factory=dict)
    data_governance_requirements: List[str] = Field(default_factory=list)
    analysis_questions: List[str] = Field(default_factory=list)
    user_responses: Dict[str, Any] = Field(default_factory=dict)


class DomainKnowledgeEnrichment(BaseModel):
    """Domain knowledge enrichment from external sources"""
    domain: str
    wikipedia_summary: Optional[str] = None
    domain_docs: List[Dict[str, Any]] = Field(default_factory=list)
    industry_standards: List[str] = Field(default_factory=list)
    best_practices: List[str] = Field(default_factory=list)
    terminology: Dict[str, str] = Field(default_factory=dict)


# ============================================================================
# WIKIPEDIA AND DOMAIN KNOWLEDGE ENRICHMENT
# ============================================================================

class DomainKnowledgeEnricher:
    """Enriches domain knowledge using Wikipedia and domain documents"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or get_llm()
    
    async def fetch_wikipedia_summary(self, domain: str) -> Optional[str]:
        """Fetch Wikipedia summary for a domain (disabled - using LLM-generated summary instead)"""
        # Wikipedia API calls disabled - use LLM-generated summary directly
        return await self._generate_domain_summary(domain)
    
    async def _generate_domain_summary(self, domain: str) -> str:
        """Generate domain summary using LLM if Wikipedia fails"""
        prompt = f"""Provide a brief summary (2-3 sentences) about the business domain: {domain}
        
        Focus on:
        - Key concepts and terminology
        - Common business processes
        - Typical data patterns
        - Industry standards"""
        
        messages = [
            SystemMessage(content="You are a domain expert providing concise domain summaries."),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, "Domain Summary Generation")
        return response.content if response else ""
    
    async def enrich_domain_knowledge(
        self, 
        domain: str,
        table_metadata: TableMetadataSummary
    ) -> DomainKnowledgeEnrichment:
        """Enrich domain knowledge from multiple sources"""
        enrichment = DomainKnowledgeEnrichment(domain=domain)
        
        # Generate domain summary using LLM (Wikipedia API disabled)
        try:
            enrichment.wikipedia_summary = await self._generate_domain_summary(domain)
        except:
            enrichment.wikipedia_summary = None
        
        # Generate industry standards and best practices using LLM
        enrichment.industry_standards = await self._identify_industry_standards(domain, table_metadata)
        enrichment.best_practices = await self._identify_best_practices(domain, table_metadata)
        enrichment.terminology = await self._extract_terminology(domain, table_metadata)
        
        return enrichment
    
    async def _identify_industry_standards(
        self, 
        domain: str, 
        table_metadata: TableMetadataSummary
    ) -> List[str]:
        """Identify relevant industry standards for the domain"""
        prompt = f"""Based on the domain "{domain}" and table "{table_metadata.table_name}",
        identify relevant industry standards, regulations, or frameworks that apply.
        
        Examples: GDPR, SOX, HIPAA, PCI-DSS, ISO standards, etc.
        
        Return as a JSON array of standard names."""
        
        messages = [
            SystemMessage(content="You are a compliance and standards expert."),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, "Industry Standards Identification", default_return=None)
        if response is None:
            return []
        
        try:
            # Try to extract JSON array
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            standards = json.loads(content)
            if isinstance(standards, list):
                # Handle both string and dict formats
                result = []
                for item in standards:
                    if isinstance(item, str):
                        result.append(item)
                    elif isinstance(item, dict):
                        # Extract description or value from dict
                        result.append(item.get('description', item.get('value', item.get('name', str(item)))))
                    else:
                        result.append(str(item))
                return result
            return []
        except:
            return []
    
    async def _identify_best_practices(
        self, 
        domain: str, 
        table_metadata: TableMetadataSummary
    ) -> List[str]:
        """Identify best practices for the domain and table type"""
        prompt = f"""Based on the domain "{domain}" and table "{table_metadata.table_name}",
        identify data modeling and analytics best practices.
        
        Consider:
        - Data quality practices
        - Naming conventions
        - Indexing strategies
        - Partitioning approaches
        - Security considerations
        
        Return as a JSON array of best practice descriptions."""
        
        messages = [
            SystemMessage(content="You are a data engineering expert."),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, "Best Practices Identification", default_return=None)
        if response is None:
            return []
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            practices = json.loads(content)
            if isinstance(practices, list):
                # Handle both string and dict formats
                result = []
                for item in practices:
                    if isinstance(item, str):
                        result.append(item)
                    elif isinstance(item, dict):
                        # Extract description or value from dict
                        result.append(item.get('description', item.get('value', item.get('name', str(item)))))
                    else:
                        result.append(str(item))
                return result
            return []
        except:
            return []
    
    async def _extract_terminology(
        self, 
        domain: str, 
        table_metadata: TableMetadataSummary
    ) -> Dict[str, str]:
        """Extract domain-specific terminology and definitions"""
        prompt = f"""Based on the domain "{domain}" and table "{table_metadata.table_name}",
        identify key domain-specific terms and their definitions.
        
        Focus on:
        - Business terms used in column names
        - Domain-specific concepts
        - Industry jargon
        
        Return as a JSON object mapping terms to definitions."""
        
        messages = [
            SystemMessage(content="You are a business analyst and domain expert."),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, "Terminology Extraction", default_return=None)
        if response is None:
            return {}
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            terminology = json.loads(content)
            return terminology if isinstance(terminology, dict) else {}
        except:
            return {}


# ============================================================================
# QUESTION GENERATION AGENT
# ============================================================================

class QuestionGenerationAgent:
    """Generates intelligent questions based on table metadata"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or get_llm()
    
    def generate_questions(
        self, 
        table_metadata: TableMetadataSummary,
        domain_knowledge: Optional[DomainKnowledgeEnrichment] = None
    ) -> Dict[str, List[str]]:
        """
        Generate questions for human-in-the-loop interaction.
        
        Returns:
            Dictionary with question categories and questions
        """
        system_prompt = """You are an expert data analyst who asks insightful questions to understand
        business requirements and data modeling needs. Generate specific, actionable questions that help:
        1. Understand business goals
        2. Identify unique keys and grain
        3. Determine analysis types
        4. Establish data governance requirements
        5. Clarify business purpose and use cases"""
        
        # Build context from metadata
        columns_info = "\n".join([
            f"- {col.name} ({col.data_type}): {col.description}"
            for col in table_metadata.columns
        ])
        
        domain_context = ""
        if domain_knowledge:
            # Safely format lists, handling both strings and other types
            def format_list(items, max_items=5):
                if not items:
                    return 'N/A'
                formatted = []
                for item in items[:max_items]:
                    if isinstance(item, str):
                        formatted.append(item)
                    elif isinstance(item, dict):
                        # Extract description or value from dict
                        formatted.append(item.get('description', item.get('value', item.get('name', str(item)))))
                    else:
                        formatted.append(str(item))
                return ', '.join(formatted) if formatted else 'N/A'
            
            domain_context = f"""
Domain Knowledge:
- Domain: {domain_knowledge.domain}
- Wikipedia Summary: {domain_knowledge.wikipedia_summary[:200] if domain_knowledge.wikipedia_summary else 'N/A'}
- Industry Standards: {format_list(domain_knowledge.industry_standards)}
- Best Practices: {format_list(domain_knowledge.best_practices)}
"""
        
        prompt = f"""Generate questions for table: {table_metadata.table_name}

Table Metadata:
- Description: {table_metadata.description}
- Business Use Case: {table_metadata.business_use_case}
- Domain: {table_metadata.domain_description}

Columns:
{columns_info}

Statistics:
- Row Count: {table_metadata.statistics.get('row_count', 'N/A')}
- Column Count: {table_metadata.statistics.get('column_count', 'N/A')}

{domain_context}

Generate questions in these categories:
1. **Analysis Type**: What kind of analysis will be performed? (descriptive, diagnostic, predictive, etc.)
2. **Unique Keys**: What columns uniquely identify a row? What is the grain?
3. **Business Goals**: What are the primary business goals this table supports?
4. **Business Purpose**: What is the main business purpose of this data?
5. **Data Governance**: What compliance, security, or governance requirements apply?
6. **Analysis Questions**: What specific questions will analysts ask of this data?

Return as JSON:
{{
    "analysis_type": ["question1", "question2"],
    "unique_keys": ["question1", "question2"],
    "business_goals": ["question1", "question2"],
    "business_purpose": ["question1"],
    "data_governance": ["question1", "question2"],
    "analysis_questions": ["question1", "question2"]
}}"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, f"Question Generation ({table_metadata.table_name})", default_return=None)
        if response is None:
            return self._get_default_questions(table_metadata)
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            questions = json.loads(content)
            return questions if isinstance(questions, dict) else {}
        except:
            # Return default questions
            return self._get_default_questions(table_metadata)
    
    def _get_default_questions(self, table_metadata: TableMetadataSummary) -> Dict[str, List[str]]:
        """Return default questions if LLM generation fails"""
        return {
            "analysis_type": [
                "What type of analysis will be performed on this table? (descriptive, diagnostic, predictive, prescriptive, exploratory)",
                "What are the primary analytical use cases for this data?"
            ],
            "unique_keys": [
                "What columns uniquely identify each row in this table?",
                "What is the grain (level of detail) of this table? (e.g., one row per order, one row per customer per day)"
            ],
            "business_goals": [
                "What are the primary business goals this table supports?",
                "What KPIs or metrics will be derived from this table?"
            ],
            "business_purpose": [
                "What is the main business purpose of this data?",
                "Who are the primary users of this data and what do they need?"
            ],
            "data_governance": [
                "Are there any compliance or regulatory requirements? (GDPR, SOX, HIPAA, etc.)",
                "What are the data retention and privacy requirements?"
            ],
            "analysis_questions": [
                "What are the top 3-5 questions analysts will ask of this data?",
                "What time-based analysis will be performed? (daily, weekly, monthly trends)"
            ]
        }


# ============================================================================
# BUSINESS GOALS AGENT
# ============================================================================

class BusinessGoalsAgent:
    """Collects and structures business goals from user input"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or get_llm()
    
    def extract_business_goals(
        self,
        user_responses: Dict[str, Any],
        table_metadata: TableMetadataSummary
    ) -> List[BusinessGoal]:
        """Extract structured business goals from user responses"""
        system_prompt = """You are a business analyst expert at extracting and structuring business goals.
        Parse user responses and create structured business goal definitions."""
        
        prompt = f"""Extract business goals from user responses:

Table: {table_metadata.table_name}
Domain: {table_metadata.domain_description}

User Responses:
{json.dumps(user_responses, indent=2)}

Extract business goals and return as JSON array:
[
    {{
        "goal_name": "goal_name",
        "description": "detailed description",
        "priority": "high|medium|low",
        "kpis": ["kpi1", "kpi2"],
        "success_metrics": ["metric1", "metric2"],
        "stakeholders": ["stakeholder1", "stakeholder2"]
    }}
]"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, "Business Goals Extraction", default_return=None)
        if response is None:
            return []
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            goals_data = json.loads(content)
            return [BusinessGoal(**goal) if isinstance(goal, dict) else BusinessGoal(goal_name=str(goal), description="") 
                    for goal in goals_data] if isinstance(goals_data, list) else []
        except:
            return []


# ============================================================================
# ANALYSIS TYPE AGENT
# ============================================================================

class AnalysisTypeAgent:
    """Determines appropriate analysis types based on user input and metadata"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or get_llm()
    
    def determine_analysis_types(
        self,
        user_responses: Dict[str, Any],
        table_metadata: TableMetadataSummary,
        business_goals: List[BusinessGoal]
    ) -> List[str]:
        """Determine analysis types based on user input and business goals"""
        system_prompt = """You are a data analytics expert. Determine the most appropriate analysis types
        for a table based on business goals, user requirements, and data characteristics."""
        
        goals_summary = "\n".join([
            f"- {goal.goal_name}: {goal.description}"
            for goal in business_goals
        ])
        
        prompt = f"""Determine analysis types for table: {table_metadata.table_name}

Business Goals:
{goals_summary}

User Responses:
{json.dumps(user_responses.get('analysis_type', {}), indent=2)}

Table Characteristics:
- Columns: {len(table_metadata.columns)}
- Has time columns: {any('date' in col.name.lower() or 'time' in col.name.lower() for col in table_metadata.columns)}
- Has numeric measures: {any(col.data_type in ['INTEGER', 'BIGINT', 'DECIMAL', 'NUMERIC', 'FLOAT', 'DOUBLE'] for col in table_metadata.columns)}

Available analysis types:
- descriptive: What happened? (summaries, aggregations)
- diagnostic: Why did it happen? (root cause analysis)
- predictive: What will happen? (forecasting, ML)
- prescriptive: What should we do? (optimization, recommendations)
- exploratory: What patterns exist? (data discovery)
- comparative: How do things compare? (A/B testing, benchmarking)
- trend: How are things changing? (time series analysis)
- segmentation: How to group data? (clustering, cohorts)
- cohort: How do groups behave over time? (cohort analysis)
- funnel: Where do users drop off? (conversion analysis)

Return as JSON array of analysis type names."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, "Analysis Type Determination", default_return=None)
        if response is None:
            return ["descriptive", "exploratory"]  # Default fallback
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            analysis_types = json.loads(content)
            return analysis_types if isinstance(analysis_types, list) else []
        except:
            return ["descriptive", "exploratory"]  # Default fallback


# ============================================================================
# UNIQUE KEYS AGENT
# ============================================================================

class UniqueKeysAgent:
    """Identifies unique keys and grain from user input and metadata"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or get_llm()
    
    def identify_unique_keys(
        self,
        user_responses: Dict[str, Any],
        table_metadata: TableMetadataSummary
    ) -> Dict[str, Any]:
        """Identify unique keys and grain from user responses and metadata"""
        system_prompt = """You are a data modeling expert. Identify unique keys and grain (level of detail)
        for a table based on user input and table structure."""
        
        columns_info = "\n".join([
            f"- {col.name} ({col.data_type}): {col.description}"
            for col in table_metadata.columns
        ])
        
        # Check statistics for uniqueness
        uniqueness_hints = ""
        if "columns" in table_metadata.statistics:
            for col_name, col_stats in table_metadata.statistics["columns"].items():
                cardinality = col_stats.get("cardinality", 0)
                row_count = table_metadata.statistics.get("row_count", 0)
                if row_count > 0 and cardinality == row_count:
                    uniqueness_hints += f"\n- {col_name}: High cardinality ({cardinality}/{row_count}) - potential unique key"
        
        prompt = f"""Identify unique keys and grain for table: {table_metadata.table_name}

Columns:
{columns_info}

Uniqueness Hints from Statistics:
{uniqueness_hints}

User Responses:
{json.dumps(user_responses.get('unique_keys', {}), indent=2)}

Return as JSON:
{{
    "primary_key": ["column1", "column2"],  // Composite key if multiple
    "unique_keys": [["key1"], ["key2", "key3"]],  // All unique key combinations
    "grain": "description of grain (e.g., 'One row per order', 'One row per customer per day')",
    "grain_type": "transaction|snapshot|accumulating_snapshot",
    "reasoning": "explanation of why these are the unique keys"
}}"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, f"Unique Keys Identification ({table_metadata.table_name})", default_return=None)
        if response is None:
            # Fallback: try to infer from column names
            return self._infer_keys_from_metadata(table_metadata)
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            keys_info = json.loads(content)
            return keys_info if isinstance(keys_info, dict) else {}
        except:
            # Fallback: try to infer from column names
            return self._infer_keys_from_metadata(table_metadata)
    
    def _infer_keys_from_metadata(self, table_metadata: TableMetadataSummary) -> Dict[str, Any]:
        """Infer unique keys from column names and metadata"""
        # Look for common primary key patterns
        potential_keys = []
        for col in table_metadata.columns:
            col_name_lower = col.name.lower()
            if any(pattern in col_name_lower for pattern in ['_id', '_key', 'id', 'pk', 'uuid']):
                potential_keys.append(col.name)
        
        grain = f"One row per {table_metadata.table_name.replace('_', ' ')}"
        
        return {
            "primary_key": potential_keys[:1] if potential_keys else [],
            "unique_keys": [potential_keys[:1]] if potential_keys else [],
            "grain": grain,
            "grain_type": "transaction",
            "reasoning": "Inferred from column naming patterns"
        }


# ============================================================================
# SEMANTIC DESCRIPTION AGENT
# ============================================================================

class SemanticDescriptionAgent:
    """Uses semantics_description.py to generate semantic descriptions"""
    
    def __init__(self):
        self.semantics_service = SemanticsDescription()
    
    async def generate_semantic_description(
        self,
        table_metadata: TableMetadataSummary
    ) -> Dict[str, Any]:
        """Generate semantic description using SemanticsDescription service"""
        # Convert TableMetadataSummary to table_data format
        table_data = {
            "name": table_metadata.table_name,
            "description": table_metadata.description or "",
            "columns": [
                {
                    "name": col.name,
                    "display_name": col.name.replace("_", " ").title(),
                    "description": col.description,
                    "data_type": col.data_type,
                    "is_primary_key": False,  # Would need to be determined
                    "is_nullable": True
                }
                for col in table_metadata.columns
            ]
        }
        
        try:
            result = await self.semantics_service.describe(
                SemanticsDescription.Input(
                    id=f"semantic_{table_metadata.table_name}",
                    table_data=table_data
                )
            )
            
            if result.status == "finished" and result.response:
                return result.response
            else:
                return {}
        except Exception as e:
            return {}


# ============================================================================
# RELATIONSHIP RECOMMENDATION AGENT
# ============================================================================

class RelationshipRecommendationAgent:
    """Uses relationship_recommendation.py to suggest relationships"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or get_llm()
    
    def recommend_relationships(
        self,
        table_metadata: TableMetadataSummary,
        all_tables: List[TableMetadataSummary]
    ) -> List[Dict[str, Any]]:
        """Recommend relationships between tables"""
        # Build MDL structure for relationship recommendation
        mdl = {
            "catalog": "temp_catalog",
            "schema": "public",
            "models": [
                {
                    "name": table_metadata.table_name,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type
                        }
                        for col in table_metadata.columns
                    ]
                }
            ],
            "relationships": []
        }
        
        # Add other tables as models
        for other_table in all_tables:
            if other_table.table_name != table_metadata.table_name:
                mdl["models"].append({
                    "name": other_table.table_name,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type
                        }
                        for col in other_table.columns
                    ]
                })
        
        # Use LLM to recommend relationships
        system_prompt = """You are a data modeling expert. Analyze table structures and recommend
        relationships between tables based on column names, data types, and business logic."""
        
        prompt = f"""Analyze this table and recommend relationships with other tables:

Current Table: {table_metadata.table_name}
Columns: {', '.join([col.name for col in table_metadata.columns])}

Other Tables:
{chr(10).join([f"- {t.table_name}: {', '.join([col.name for col in t.columns[:5]])}" for t in all_tables if t.table_name != table_metadata.table_name])}

Recommend relationships and return as JSON array:
[
    {{
        "related_table": "table_name",
        "relationship_type": "ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY",
        "join_condition": "current_table.column = related_table.column",
        "confidence": 0.0-1.0,
        "reasoning": "explanation"
    }}
]"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = safe_llm_invoke(self.llm, messages, f"Relationship Recommendation ({table_metadata.table_name})", default_return=None)
        if response is None:
            return []
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            relationships = json.loads(content)
            return relationships if isinstance(relationships, list) else []
        except:
            return []


# ============================================================================
# MAIN HUMAN-IN-THE-LOOP AGENT
# ============================================================================

class SilverHumanInLoopAgent:
    """Main agent orchestrating human-in-the-loop interactions for silver workflow"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        user_input_handler: Optional[Any] = None,
        enable_data_mart_planning: bool = True
    ):
        # Use get_llm() to ensure API key from settings is used
        self.llm = llm or get_llm()
        self.user_input_handler = user_input_handler  # Function to get user input
        self.enable_data_mart_planning = enable_data_mart_planning
        
        # Initialize sub-agents
        self.domain_enricher = DomainKnowledgeEnricher(llm=self.llm)
        self.question_generator = QuestionGenerationAgent(llm=self.llm)
        self.business_goals_agent = BusinessGoalsAgent(llm=self.llm)
        self.analysis_type_agent = AnalysisTypeAgent(llm=self.llm)
        self.unique_keys_agent = UniqueKeysAgent(llm=self.llm)
        self.semantic_agent = SemanticDescriptionAgent()
        self.relationship_agent = RelationshipRecommendationAgent(llm=self.llm)
        
        # Initialize data mart planner if enabled
        if self.enable_data_mart_planning:
            # Import SQL generator here to avoid circular dependency
            from app.agents.cubes.sql_generator_agent import SQLGeneratorAgent
            sql_generator = SQLGeneratorAgent(llm=self.llm)
            self.data_mart_planner = DataMartPlannerAgent(llm=self.llm, sql_generator=sql_generator)
        else:
            self.data_mart_planner = None
    
    def update_llm(self, llm: ChatOpenAI):
        """
        Update the LLM instance for this agent and all sub-agents.
        This ensures all agents use the same LLM instance with the correct API key.
        
        Args:
            llm: The LLM instance to use
        """
        self.llm = llm
        # Update all sub-agents
        if hasattr(self, 'domain_enricher'):
            self.domain_enricher.llm = llm
        if hasattr(self, 'question_generator'):
            self.question_generator.llm = llm
        if hasattr(self, 'business_goals_agent'):
            self.business_goals_agent.llm = llm
        if hasattr(self, 'analysis_type_agent'):
            self.analysis_type_agent.llm = llm
        if hasattr(self, 'unique_keys_agent'):
            self.unique_keys_agent.llm = llm
        if hasattr(self, 'relationship_agent'):
            self.relationship_agent.llm = llm
        if hasattr(self, 'data_mart_planner') and self.data_mart_planner:
            self.data_mart_planner.llm = llm
    
    async def collect_table_requirements(
        self,
        state: AgentState,
        table_metadata: TableMetadataSummary,
        all_tables: List[TableMetadataSummary]
    ) -> TableAnalysisConfig:
        """
        Main method to collect requirements for a single table through human-in-the-loop.
        
        Args:
            state: Current agent state
            table_metadata: Metadata for the table being analyzed
            all_tables: All tables in the dataset for relationship analysis
            
        Returns:
            TableAnalysisConfig with collected requirements
        """
        config = TableAnalysisConfig(table_name=table_metadata.table_name)
        
        # Step 1: Enrich domain knowledge
        print(f"\n🔍 Step 1: Enriching domain knowledge for {table_metadata.table_name}...")
        domain = table_metadata.domain_description or table_metadata.business_use_case or "general"
        domain_knowledge = await self.domain_enricher.enrich_domain_knowledge(
            domain=domain,
            table_metadata=table_metadata
        )
        config.domain_knowledge = domain_knowledge.dict()
        
        # Step 2: Generate semantic description
        print(f"📝 Step 2: Generating semantic description...")
        semantic_desc = await self.semantic_agent.generate_semantic_description(table_metadata)
        if semantic_desc:
            config.domain_knowledge["semantic_description"] = semantic_desc
        
        # Step 3: Generate questions
        print(f"❓ Step 3: Generating questions...")
        questions = self.question_generator.generate_questions(
            table_metadata=table_metadata,
            domain_knowledge=domain_knowledge
        )
        config.analysis_questions = [
            q for category_questions in questions.values() for q in category_questions
        ]
        
        # Step 4: Collect user responses (human-in-the-loop)
        print(f"👤 Step 4: Collecting user responses...")
        user_responses = await self._collect_user_responses(
            table_metadata=table_metadata,
            questions=questions,
            domain_knowledge=domain_knowledge
        )
        config.user_responses = user_responses
        
        # Step 5: Extract business goals
        print(f"🎯 Step 5: Extracting business goals...")
        business_goals = self.business_goals_agent.extract_business_goals(
            user_responses=user_responses,
            table_metadata=table_metadata
        )
        config.business_goals = business_goals
        
        # Step 6: Determine analysis types
        print(f"📊 Step 6: Determining analysis types...")
        analysis_types = self.analysis_type_agent.determine_analysis_types(
            user_responses=user_responses,
            table_metadata=table_metadata,
            business_goals=business_goals
        )
        config.analysis_types = analysis_types
        
        # Step 7: Identify unique keys
        print(f"🔑 Step 7: Identifying unique keys...")
        keys_info = self.unique_keys_agent.identify_unique_keys(
            user_responses=user_responses,
            table_metadata=table_metadata
        )
        config.unique_keys = keys_info.get("primary_key", [])
        config.domain_knowledge["grain"] = keys_info.get("grain", "")
        config.domain_knowledge["grain_type"] = keys_info.get("grain_type", "transaction")
        
        # Step 8: Extract business purpose
        config.business_purpose = user_responses.get("business_purpose", {}).get("response", table_metadata.business_use_case)
        
        # Step 9: Extract data governance requirements
        config.data_governance_requirements = user_responses.get("data_governance", {}).get("response", [])
        if isinstance(config.data_governance_requirements, str):
            config.data_governance_requirements = [config.data_governance_requirements]
        
        # Step 10: Recommend relationships
        print(f"🔗 Step 10: Recommending relationships...")
        relationships = self.relationship_agent.recommend_relationships(
            table_metadata=table_metadata,
            all_tables=all_tables
        )
        config.domain_knowledge["recommended_relationships"] = relationships
        
        return config
    
    async def plan_data_marts_from_goal(
        self,
        goal: str,
        state: AgentState,
        project_id: Optional[str] = None
    ) -> DataMartPlan:
        """
        Plan data marts from a business goal using silver table retrieval.
        
        Args:
            goal: Natural language description of the data mart goal
            state: Current agent state with table metadata
            project_id: Optional project ID
            
        Returns:
            DataMartPlan with SQL definitions and natural language questions
        """
        if not self.data_mart_planner:
            raise ValueError("Data mart planning is not enabled. Set enable_data_mart_planning=True")
        
        print(f"\n📊 Planning data mart for goal: {goal}")
        
        # Get available silver tables from state
        available_tables = state.get("table_metadata", [])
        
        # Get business goals from state if available
        business_goals = None
        table_configs = state.get("table_analysis_configs", [])
        if table_configs:
            # Extract business goals from table configs
            all_goals = []
            for config in table_configs:
                if isinstance(config, dict):
                    goals = config.get("business_goals", [])
                    all_goals.extend(goals)
            if all_goals:
                business_goals = all_goals
        
        # Plan the data mart
        plan = await self.data_mart_planner.plan_data_mart(
            goal=goal,
            business_goals=business_goals,
            available_silver_tables=available_tables,
            project_id=project_id
        )
        
        # Update state with the plan
        state = self.data_mart_planner.convert_to_agent_state_updates(plan, state)
        
        print(f"✅ Generated {len(plan.marts)} data mart(s)")
        for i, mart in enumerate(plan.marts, 1):
            print(f"   {i}. {mart.mart_name}")
            print(f"      Question: {mart.natural_language_question}")
        
        return plan
    
    async def _collect_user_responses(
        self,
        table_metadata: TableMetadataSummary,
        questions: Dict[str, List[str]],
        domain_knowledge: DomainKnowledgeEnrichment
    ) -> Dict[str, Any]:
        """
        Collect user responses to questions.
        In production, this would interact with a UI/API.
        For now, uses LLM to simulate user responses based on metadata.
        """
        responses = {}
        
        # If user_input_handler is provided, use it
        if self.user_input_handler:
            for category, category_questions in questions.items():
                category_responses = []
                for question in category_questions:
                    user_input = await self.user_input_handler(
                        table_name=table_metadata.table_name,
                        question=question,
                        context={
                            "domain_knowledge": domain_knowledge.dict(),
                            "table_metadata": table_metadata.dict()
                        }
                    )
                    category_responses.append(user_input)
                responses[category] = {"questions": category_questions, "response": category_responses}
        else:
            # Simulate user responses using LLM (for testing/demo)
            for category, category_questions in questions.items():
                # Use LLM to generate realistic responses based on metadata
                prompt = f"""Based on this table metadata, provide realistic user responses to these questions:

Table: {table_metadata.table_name}
Description: {table_metadata.description}
Business Use Case: {table_metadata.business_use_case}
Domain: {table_metadata.domain_description}

Questions:
{chr(10).join([f"- {q}" for q in category_questions])}

Provide a realistic response that a business user might give. Be specific and business-focused."""
                
                messages = [
                    SystemMessage(content="You are a business user providing requirements for data analysis."),
                    HumanMessage(content=prompt)
                ]
                response = safe_llm_invoke(self.llm, messages, f"Simulated User Response ({category})", default_return=None)
                if response is None:
                    # Use a default response if LLM fails
                    response_content = f"Default response for {category} category"
                else:
                    response_content = response.content
                
                responses[category] = {
                    "questions": category_questions,
                    "response": response_content
                }
        
        return responses
    
    def convert_to_lod_config(
        self,
        table_config: TableAnalysisConfig
    ) -> Optional[LODConfig]:
        """Convert TableAnalysisConfig to LODConfig"""
        if not table_config.unique_keys:
            return None
        
        return LODConfig(
            table_name=table_config.table_name,
            lod_type="FIXED",
            dimensions=table_config.unique_keys,
            description=f"LOD based on unique keys: {', '.join(table_config.unique_keys)}"
        )
    
    def convert_to_relationship_mappings(
        self,
        table_config: TableAnalysisConfig,
        all_configs: List[TableAnalysisConfig]
    ) -> List[RelationshipMapping]:
        """Convert recommended relationships to RelationshipMapping objects"""
        relationships = []
        recommended = table_config.domain_knowledge.get("recommended_relationships", [])
        
        for rel in recommended:
            related_table = rel.get("related_table")
            # Find the related table config
            related_config = next(
                (c for c in all_configs if c.table_name == related_table),
                None
            )
            
            if related_config:
                join_condition = rel.get("join_condition", "")
                # Extract join type
                rel_type = rel.get("relationship_type", "MANY_TO_ONE")
                
                relationships.append(RelationshipMapping(
                    child_table=table_config.table_name,
                    parent_table=related_table,
                    join_type=rel_type,
                    join_condition=join_condition,
                    layer="silver"
                ))
        
        return relationships


# ============================================================================
# INTEGRATION WITH SILVER WORKFLOW
# ============================================================================

async def enrich_silver_workflow_with_human_in_loop(
    state: AgentState,
    human_in_loop_agent: SilverHumanInLoopAgent,
    data_mart_goals: Optional[List[str]] = None
) -> AgentState:
    """
    Enrich silver workflow state with human-in-the-loop collected requirements.
    This should be called after enrich_table_metadata and before collect_requirements.
    
    Args:
        state: Current agent state
        human_in_loop_agent: The human-in-the-loop agent instance
        data_mart_goals: Optional list of data mart goals to plan
    """
    table_configs = []
    all_tables = state.get("table_metadata", [])
    
    # Collect requirements for each table
    for table_metadata in all_tables:
        print(f"\n{'='*60}")
        print(f"Processing table: {table_metadata.table_name}")
        print(f"{'='*60}")
        
        config = await human_in_loop_agent.collect_table_requirements(
            state=state,
            table_metadata=table_metadata,
            all_tables=all_tables
        )
        
        table_configs.append(config)
        
        # Convert to LOD config
        lod_config = human_in_loop_agent.convert_to_lod_config(config)
        if lod_config:
            if "lod_configs" not in state:
                state["lod_configs"] = []
            state["lod_configs"].append(lod_config)
        
        # Convert to relationship mappings
        relationship_mappings = human_in_loop_agent.convert_to_relationship_mappings(
            table_config=config,
            all_configs=table_configs
        )
        if relationship_mappings:
            if "relationship_mappings" not in state:
                state["relationship_mappings"] = []
            state["relationship_mappings"].extend(relationship_mappings)
    
    # Store table configs in state
    state["table_analysis_configs"] = [config.dict() for config in table_configs]
    
    # Plan data marts if goals are provided and planning is enabled
    if data_mart_goals and human_in_loop_agent.enable_data_mart_planning:
        print(f"\n{'='*60}")
        print(f"Planning Data Marts")
        print(f"{'='*60}")
        
        for goal in data_mart_goals:
            try:
                plan = await human_in_loop_agent.plan_data_marts_from_goal(
                    goal=goal,
                    state=state,
                    project_id=state.get("project_id")
                )
                print(f"\n✅ Planned data mart for: {goal}")
            except Exception as e:
                logger.error(f"Error planning data mart for goal '{goal}': {str(e)}")
                continue
    
    # Add summary message
    summary = f"Collected human-in-the-loop requirements for {len(table_configs)} tables."
    if data_mart_goals:
        summary += f" Planned {len(data_mart_goals)} data mart goal(s)."
    state["messages"].append(AIMessage(content=summary))
    
    return state

