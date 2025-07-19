import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger("SemanticRouter")

class AgentType(str, Enum):
    """Types of specialized agentic in the system."""
    PLANNER = "planner"
    EXECUTOR = "executor"
    SELF_RAG = "self_rag"

class RoutingDecision(BaseModel):
    """The result of a routing decision by the semantic router."""
    primary_agent: AgentType
    confidence: float = Field(ge=0.0, le=1.0)
    secondary_agents: List[AgentType] = Field(default_factory=list)
    reasoning: str
    agent_specific_params: Dict[str, Any] = Field(default_factory=dict)

class SemanticRouter:
    """
    Routes questions to the appropriate specialized agent based on 
    semantic analysis of the question content.
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the semantic router."""
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
    
    async def route_question(
        self, 
        question: str,
        chat_history: List[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """
        Analyze a question and determine which agent should handle it.
        
        Args:
            question: The user's question
            chat_history: Optional conversation history
            
        Returns:
            A RoutingDecision indicating which agent(s) should process the question
        """
        system_prompt = """You are an expert router for a document question answering system.
        Your task is to analyze the user's question and determine which specialized agent 
        should handle it. The available agentic are:

        1. PLANNER - Responsible for creating execution plans for complex questions that require
           multiple steps or data sources. The planner analyzes questions, identifies relevant sources,
           and creates step-by-step plans but does not execute them.
           
        2. EXECUTOR - Responsible for executing specific steps or operations against data sources.
           The executor carries out well-defined operations like querying Salesforce objects,
           retrieving Gong call transcripts, or extracting document content.
           
        3. SELF_RAG - Specialized in document retrieval and analysis when the question is primarily
           about document content and requires semantic search and analysis of text.
           
        Your task is to decide:
        1. Which agent should be the PRIMARY handler of this question
        2. Which agent(s) might be needed as SECONDARY handlers
        3. How confident you are in this routing decision (0.0 to 1.0)
        4. Your reasoning for this decision
        5. Any specific parameters that should be passed to the agentic
        
        For example:
        - "What are our top 5 opportunities by value?" → EXECUTOR (clear Salesforce operation)
        - "Find documents about our marketing strategy" → SELF_RAG (document retrieval)
        - "Show me Gong calls where Company X mentioned our product, and check if they have open opportunities" → PLANNER (needs coordination between multiple sources)
        
        Format your response as a JSON object with these keys:
        {
            "primary_agent": "PLANNER|EXECUTOR|SELF_RAG",
            "confidence": 0.85,
            "secondary_agents": ["AGENT1", "AGENT2"],
            "reasoning": "Explanation of your decision",
            "agent_specific_params": {
                "param_name": "param_value"
            }
        }
        """
        
        # Prepare context with chat history if available
        context = f"Question: {question}\n\n"
        
        if chat_history:
            # Format recent chat history for context
            formatted_history = []
            for msg in chat_history[-3:]:  # Include last 3 messages for context
                role = "User" if msg.get("message_type") == "human" else "Assistant"
                formatted_history.append(f"{role}: {msg.get('message_content', '')}")
            
            context += f"Recent conversation history:\n{chr(10).join(formatted_history)}\n\n"
            
        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Please analyze this question and determine the appropriate agent:\n\n{context}")
                ]
            )
            
            # Parse the JSON response
            import json
            import re
            
            # Extract JSON from the response
            json_match = re.search(r'{.*}', response.content, re.DOTALL)
            if json_match:
                decision_dict = json.loads(json_match.group(0))
                
                # Convert string agent types to enum values
                primary_agent_str = decision_dict.get("primary_agent", "").upper()
                primary_agent = AgentType.PLANNER  # Default
                
                if primary_agent_str == "EXECUTOR":
                    primary_agent = AgentType.EXECUTOR
                elif primary_agent_str == "SELF_RAG":
                    primary_agent = AgentType.SELF_RAG
                
                # Convert secondary agentic
                secondary_agents = []
                for agent_str in decision_dict.get("secondary_agents", []):
                    agent_str = agent_str.upper()
                    if agent_str == "PLANNER":
                        secondary_agents.append(AgentType.PLANNER)
                    elif agent_str == "EXECUTOR":
                        secondary_agents.append(AgentType.EXECUTOR)
                    elif agent_str == "SELF_RAG":
                        secondary_agents.append(AgentType.SELF_RAG)
                
                return RoutingDecision(
                    primary_agent=primary_agent,
                    confidence=decision_dict.get("confidence", 0.7),
                    secondary_agents=secondary_agents,
                    reasoning=decision_dict.get("reasoning", ""),
                    agent_specific_params=decision_dict.get("agent_specific_params", {})
                )
            else:
                logger.error("Failed to extract JSON from LLM response")
                # Default routing decision
                return RoutingDecision(
                    primary_agent=AgentType.PLANNER,
                    confidence=0.5,
                    secondary_agents=[],
                    reasoning="Failed to parse router response. Defaulting to planner.",
                    agent_specific_params={}
                )
                
        except Exception as e:
            logger.error(f"Error in semantic routing: {e}")
            # Default routing decision
            return RoutingDecision(
                primary_agent=AgentType.PLANNER,
                confidence=0.5,
                secondary_agents=[],
                reasoning=f"Error in routing: {str(e)}. Defaulting to planner.",
                agent_specific_params={}
            )
    
    async def coordinate_agents(
        self,
        question: str,
        routing_decision: RoutingDecision,
        agents: Dict[AgentType, Any],
        chat_history: List[Dict[str, Any]] = None,
        data_stores: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Coordinate the execution of agentic based on the routing decision.
        
        Args:
            question: The user's question
            routing_decision: The routing decision from route_question
            agents: Dictionary mapping agent types to agent instances
            chat_history: Optional conversation history
            data_stores: Optional data stores for agent execution
            
        Returns:
            The final response to the user's question
        """
        start_time = time.time()
        logger.info(f"Coordinating agentic for question: {question}")
        logger.info(f"Primary agent: {routing_decision.primary_agent}, confidence: {routing_decision.confidence}")
        
        # Different coordination flows based on primary agent
        if routing_decision.primary_agent == AgentType.PLANNER:
            return await self._coordinate_planner_flow(
                question, routing_decision, agents, chat_history, data_stores
            )
        elif routing_decision.primary_agent == AgentType.EXECUTOR:
            return await self._coordinate_executor_flow(
                question, routing_decision, agents, chat_history, data_stores
            )
        elif routing_decision.primary_agent == AgentType.SELF_RAG:
            return await self._coordinate_self_rag_flow(
                question, routing_decision, agents, chat_history, data_stores
            )
        else:
            logger.error(f"Unknown primary agent type: {routing_decision.primary_agent}")
            return {
                "error": f"Unknown agent type: {routing_decision.primary_agent}",
                "question": question
            }
    
    async def _coordinate_planner_flow(
        self,
        question: str,
        routing_decision: RoutingDecision,
        agents: Dict[AgentType, Any],
        chat_history: List[Dict[str, Any]] = None,
        data_stores: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Coordinate a flow where the planner is the primary agent."""
        planner = agents.get(AgentType.PLANNER)
        executor = agents.get(AgentType.EXECUTOR)
        
        if not planner:
            logger.error("Planner agent not available")
            return {"error": "Planner agent not available", "question": question}
            
        if not executor and AgentType.EXECUTOR in routing_decision.secondary_agents:
            logger.error("Executor agent not available but required as secondary")
            return {"error": "Executor agent not available but required", "question": question}
        
        # Step 1: Generate a plan
        plan = await planner.plan(
            question=question,
            chat_history=chat_history,
            params=routing_decision.agent_specific_params.get("planner", {})
        )
        
        # Step 2: If executor is needed, execute the plan
        if AgentType.EXECUTOR in routing_decision.secondary_agents and executor:
            execution_results = await executor.execute_plan(
                plan=plan,
                data_stores=data_stores,
                params=routing_decision.agent_specific_params.get("executor", {})
            )
            
            # Return the execution results
            return {
                "question": question,
                "plan": plan.dict(),
                "execution_results": execution_results,
                "processing_time": time.time() - start_time
            }
        else:
            # Return just the plan if no execution is needed
            return {
                "question": question,
                "plan": plan.dict(),
                "processing_time": time.time() - start_time
            }
    
    async def _coordinate_executor_flow(
        self,
        question: str,
        routing_decision: RoutingDecision,
        agents: Dict[AgentType, Any],
        chat_history: List[Dict[str, Any]] = None,
        data_stores: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Coordinate a flow where the executor is the primary agent."""
        executor = agents.get(AgentType.EXECUTOR)
        
        if not executor:
            logger.error("Executor agent not available")
            return {"error": "Executor agent not available", "question": question}
        
        # For direct execution, the executor needs to handle both planning and execution
        execution_results = await executor.execute_direct(
            question=question,
            chat_history=chat_history,
            data_stores=data_stores,
            params=routing_decision.agent_specific_params.get("executor", {})
        )
        
        return {
            "question": question,
            "execution_results": execution_results,
            "processing_time": time.time() - start_time
        }
    
    async def _coordinate_self_rag_flow(
        self,
        question: str,
        routing_decision: RoutingDecision,
        agents: Dict[AgentType, Any],
        chat_history: List[Dict[str, Any]] = None,
        data_stores: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Coordinate a flow where the Self-RAG is the primary agent."""
        self_rag = agents.get(AgentType.SELF_RAG)
        
        if not self_rag:
            logger.error("Self-RAG agent not available")
            return {"error": "Self-RAG agent not available", "question": question}
        start_time = time.time()
        # For Self-RAG, we directly pass the question to the Self-RAG agent
        rag_results = await self_rag.process(
            question=question,
            chat_history=chat_history,
            params=routing_decision.agent_specific_params.get("self_rag", {})
        )
        
        return {
            "question": question,
            "rag_results": rag_results,
            "processing_time": time.time() - start_time
        }