"""
Data Mart Planner Agent

This agent plans data marts by:
1. Using silver table retrieval to find relevant tables
2. Generating SQL to create data marts
3. Generating natural language questions for each SQL
4. Integrating with silver human-in-the-loop workflow
"""

import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
import json

from app.agents.cubes.silver_table_retrieval import SilverTableRetrieval, SilverTableRetrievalResults
# Note: TableMetadataSummary and AgentState imported lazily to avoid circular dependency
from app.core.dependencies import get_llm
from app.agents.cubes.sql_generator_agent import SQLGeneratorAgent, SQLType, SQLDialect

logger = logging.getLogger("genieml-agents")


def log_llm_call(stage: str, messages: List, response: Any, max_response_length: int = 500):
    """
    Log LLM request and response for debugging.
    
    Args:
        stage: Name of the stage/operation
        messages: List of messages sent to LLM
        response: LLM response object
        max_response_length: Maximum length of response to log (truncate if longer)
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    
    system_msg = next((msg.content for msg in messages if isinstance(msg, SystemMessage)), None)
    user_msg = next((msg.content for msg in messages if isinstance(msg, HumanMessage)), None)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🤖 LLM CALL: {stage}")
    logger.info(f"{'='*80}")
    
    if system_msg:
        logger.debug(f"System Message: {system_msg[:200]}...")
    
    if user_msg:
        user_preview = user_msg[:300] + "..." if len(user_msg) > 300 else user_msg
        logger.info(f"User Prompt Preview: {user_preview}")
    
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


class DataMartSQL(BaseModel):
    """SQL definition for a data mart."""
    mart_name: str
    sql: str
    description: str
    natural_language_question: str
    source_tables: List[str] = Field(default_factory=list)
    target_columns: List[str] = Field(default_factory=list)
    business_value: str = ""
    grain: str = ""  # Level of detail
    associated_metrics: List[Dict[str, Any]] = Field(default_factory=list)  # Metrics associated with this specific mart


class DataMartPlan(BaseModel):
    """Complete data mart plan."""
    goal: str
    marts: List[DataMartSQL]
    reasoning: str
    estimated_complexity: str = "medium"
    associated_metrics: List[Dict[str, Any]] = Field(default_factory=list)  # Metrics associated with this goal


class DataMartPlannerAgent:
    """Plans data marts from silver tables."""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        silver_table_retrieval: Optional[SilverTableRetrieval] = None,
        model_name: str = "gpt-4o",
        sql_generator: Optional[SQLGeneratorAgent] = None
    ):
        """Initialize the data mart planner agent.
        
        Args:
            llm: Optional LLM instance
            silver_table_retrieval: Optional silver table retrieval agent
            model_name: LLM model name
            sql_generator: Optional SQL generator agent
        """
        self.llm = llm or get_llm()
        self.silver_retrieval = silver_table_retrieval or SilverTableRetrieval(model_name=model_name)
        self.parser = JsonOutputParser()
        self.sql_generator = sql_generator or SQLGeneratorAgent(llm=self.llm, model_name=model_name)
    
    async def plan_data_mart(
        self,
        goal: str,
        business_goals: Optional[List[Dict[str, Any]]] = None,
        available_silver_tables: Optional[List[Any]] = None,  # TableMetadataSummary imported lazily
        project_id: Optional[str] = None
    ) -> DataMartPlan:
        """
        Plan a data mart based on a business goal.
        
        Args:
            goal: Natural language description of the data mart goal
            business_goals: Optional list of business goals
            available_silver_tables: Optional list of available silver table metadata
            project_id: Optional project ID
            
        Returns:
            DataMartPlan with SQL definitions and questions
        """
        logger.info(f"Planning data mart for goal: {goal}")
        
        # Step 1: Retrieve relevant silver tables
        logger.info("Step 1: Retrieving relevant silver tables...")
        
        # Convert TableMetadataSummary to dict format for retrieval
        # Import here to avoid circular dependency
        from app.agents.cubes.cube_generation_agent import TableMetadataSummary
        
        tables_dict = None
        if available_silver_tables:
            tables_dict = [
                {
                    "table_name": table.table_name,
                    "description": table.description or "",
                    "columns": [
                        {
                            "name": col.name,
                            "data_type": col.data_type,
                            "description": col.description or ""
                        }
                        for col in table.columns
                    ],
                    "domain_description": table.domain_description or "",
                    "business_use_case": table.business_use_case or "",
                    "relationships": table.relationships or []
                }
                for table in available_silver_tables
            ]
        
        retrieval_results = await self.silver_retrieval.retrieve_silver_tables(
            query=goal,
            business_goals=business_goals,
            project_id=project_id,
            available_silver_tables=tables_dict
        )
        
        logger.info(f"Retrieved {len(retrieval_results.tables)} relevant tables")
        
        if not retrieval_results.tables:
            logger.warning("No relevant tables found, returning empty plan")
            return DataMartPlan(
                goal=goal,
                marts=[],
                reasoning="No relevant silver tables found for this goal",
                estimated_complexity="low"
            )
        
        # Step 2: Generate data mart SQL and questions
        logger.info("Step 2: Generating data mart SQL and questions...")
        marts = await self._generate_data_mart_sqls(
            goal=goal,
            selected_tables=retrieval_results.tables,
            business_goals=business_goals,
            available_tables=available_silver_tables
        )
        
        # Step 3: Generate overall reasoning
        reasoning = self._generate_reasoning(goal, retrieval_results, marts)
        
        return DataMartPlan(
            goal=goal,
            marts=marts,
            reasoning=reasoning,
            estimated_complexity=self._estimate_complexity(marts)
        )
    
    async def _generate_data_mart_sqls(
        self,
        goal: str,
        selected_tables: List[Any],
        business_goals: Optional[List[Dict[str, Any]]],
        available_tables: Optional[List[Any]]  # TableMetadataSummary imported lazily
    ) -> List[DataMartSQL]:
        """Generate SQL definitions for data marts."""
        
        system_prompt = """You are a data engineering expert specializing in creating data marts from silver tables.

Your task is to:
1. Generate SQL CREATE TABLE statements for data marts
2. Create natural language questions that each SQL answers
3. Ensure SQL follows best practices (proper joins, aggregations, etc.)
4. Document the grain and business value

Guidelines:
- Use proper SQL syntax (CREATE TABLE AS SELECT)
- Include appropriate JOINs when multiple tables are needed
- Add WHERE clauses for filtering when relevant
- Use aggregations (SUM, COUNT, AVG) when appropriate
- Document the grain (e.g., "One row per customer per day")
- Generate clear, business-focused natural language questions

Return JSON array with data mart definitions."""
        
        # Build table information for the prompt
        tables_info = []
        for selected_table in selected_tables:
            table_name = selected_table.table_name if hasattr(selected_table, 'table_name') else selected_table.get('table_name', '')
            
            # Find full table metadata if available
            table_metadata = None
            if available_tables:
                table_metadata = next(
                    (t for t in available_tables if t.table_name == table_name),
                    None
                )
            
            if table_metadata:
                table_info = {
                    "name": table_metadata.table_name,
                    "description": table_metadata.description or "",
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type,
                            "description": col.description or ""
                        }
                        for col in table_metadata.columns
                    ],
                    "relationships": table_metadata.relationships or []
                }
            else:
                # Use selected table info
                table_info = {
                    "name": table_name,
                    "description": "",
                    "columns": selected_table.columns if hasattr(selected_table, 'columns') else selected_table.get('columns', []),
                    "relationships": selected_table.relationships if hasattr(selected_table, 'relationships') else selected_table.get('relationships', [])
                }
            
            tables_info.append(table_info)
        
        goals_text = ""
        if business_goals:
            goals_text = "\n".join([
                f"- {goal.get('goal_name', '')}: {goal.get('description', '')}"
                for goal in business_goals
            ])
        
        user_prompt = f"""Generate data mart SQL definitions for this goal:

Goal: {goal}

Business Goals:
{goals_text}

Selected Silver Tables:
{json.dumps(tables_info, indent=2)}

Generate 1-3 data marts that answer this goal. For each data mart, provide:

1. A descriptive mart name (e.g., "customer_sales_summary_daily")
2. Complete SQL CREATE TABLE statement
3. A natural language question this SQL answers
4. Source tables used
5. Target columns in the result
6. Business value description
7. Grain description

Return as JSON array:
[
    {{
        "mart_name": "mart_name",
        "sql": "CREATE TABLE ... AS SELECT ...",
        "description": "What this mart contains",
        "natural_language_question": "What question does this SQL answer?",
        "source_tables": ["table1", "table2"],
        "target_columns": ["col1", "col2"],
        "business_value": "Why this mart is valuable",
        "grain": "One row per ..."
    }}
]"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            log_llm_call(f"Data Mart SQL Generation ({goal[:50]})", messages, response, max_response_length=1000)
            
            # Parse response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            marts_data = json.loads(content)
            if isinstance(marts_data, dict) and "marts" in marts_data:
                marts_data = marts_data["marts"]
            
            # Convert to DataMartSQL objects
            marts = []
            for mart_data in marts_data:
                try:
                    mart = DataMartSQL(**mart_data)
                    marts.append(mart)
                except Exception as e:
                    logger.warning(f"Error parsing mart data: {str(e)}")
                    continue
            
            return marts
            
        except Exception as e:
            logger.error(f"Error generating data mart SQLs: {str(e)}")
            # Return a basic fallback mart
            return [self._create_fallback_mart(goal, selected_tables)]
    
    def _create_fallback_mart(
        self,
        goal: str,
        selected_tables: List[Any]
    ) -> DataMartSQL:
        """Create a basic fallback data mart."""
        if not selected_tables:
            table_name = "unknown_table"
        else:
            table_name = selected_tables[0].table_name if hasattr(selected_tables[0], 'table_name') else selected_tables[0].get('table_name', 'unknown_table')
        
        mart_name = f"data_mart_{table_name}"
        sql = f"""CREATE TABLE {mart_name} AS
SELECT *
FROM {table_name}
LIMIT 1000;"""
        
        return DataMartSQL(
            mart_name=mart_name,
            sql=sql,
            description=f"Basic data mart for goal: {goal}",
            natural_language_question=f"What data is available in {table_name}?",
            source_tables=[table_name],
            target_columns=[],
            business_value=f"Provides access to {table_name} data",
            grain="One row per record"
        )
    
    def _generate_reasoning(
        self,
        goal: str,
        retrieval_results: SilverTableRetrievalResults,
        marts: List[DataMartSQL]
    ) -> str:
        """Generate reasoning for the data mart plan."""
        table_names = [t.table_name if hasattr(t, 'table_name') else t.get('table_name', '') for t in retrieval_results.tables]
        
        reasoning = f"""Planned data mart for goal: "{goal}"

Selected {len(retrieval_results.tables)} relevant silver tables: {', '.join(table_names)}

Generated {len(marts)} data mart(s):
"""
        for i, mart in enumerate(marts, 1):
            reasoning += f"\n{i}. {mart.mart_name}: {mart.description}\n"
            reasoning += f"   - Answers: {mart.natural_language_question}\n"
            reasoning += f"   - Grain: {mart.grain}\n"
        
        return reasoning
    
    def _estimate_complexity(self, marts: List[DataMartSQL]) -> str:
        """Estimate complexity based on number of marts and SQL complexity."""
        if not marts:
            return "low"
        
        total_tables = sum(len(mart.source_tables) for mart in marts)
        avg_tables_per_mart = total_tables / len(marts)
        
        if avg_tables_per_mart > 3 or len(marts) > 3:
            return "high"
        elif avg_tables_per_mart > 1 or len(marts) > 1:
            return "medium"
        else:
            return "low"
    
    def convert_to_agent_state_updates(
        self,
        plan: DataMartPlan,
        state: Any  # AgentState imported lazily
    ) -> Any:  # Returns AgentState
        """Convert data mart plan to agent state updates."""
        
        # Store data mart plans in state
        if "data_mart_plans" not in state:
            state["data_mart_plans"] = []
        
        state["data_mart_plans"].append({
            "goal": plan.goal,
            "marts": [mart.dict() for mart in plan.marts],
            "reasoning": plan.reasoning,
            "complexity": plan.estimated_complexity
        })
        
        # Add messages
        from langchain_core.messages import AIMessage
        summary = f"Planned data mart for goal: {plan.goal}. Generated {len(plan.marts)} data mart(s)."
        state["messages"].append(AIMessage(content=summary))
        
        return state

