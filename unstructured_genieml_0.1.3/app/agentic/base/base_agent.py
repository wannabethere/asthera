import time
import json
from typing import Any, Dict, List, Optional
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI

from app.config.agent_config import get_agent_config
from app.schemas.document_schemas import DocumentSource
from app.agentic.utils.document_processor import process_retrieved_documents, format_documents_for_context
from app.agentic.utils.prompt_builder import build_human_prompt
from app.utils.llm_factory import get_default_llm, get_answer_generation_llm
from app.utils.logging_config import setup_agent_logger

# Set up logging using the centralized configuration
logger = setup_agent_logger("BaseAgent")

class AgentState(BaseModel):
    """Base state for all agentic. Specialized agentic can extend this."""
    question: str
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    # Add insight packages to avoid flattening/reconstructing relationships
    insight_packages: List[Dict[str, Any]] = Field(default_factory=list)
    answer: str = ""
    document_ids: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    additional_context: Dict[str, Any] = Field(default_factory=dict)
    source_type: str = "generic"
    
    # Added fields for refinement process
    original_question: str = ""
    current_query: str = ""
    query_type: str = "initial"
    needs_refinement: bool = False
    recursion_count: int = 0
    
    def __post_init__(self):
        # Initialize original and current query if not provided
        if not self.original_question:
            self.original_question = self.question
        if not self.current_query:
            self.current_query = self.question

class BaseAgent(ABC):
    """
    Abstract base class for all specialized agentic.
    This defines the common interface all agentic must implement.
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None, source_type: str = "generic"):
        """Initialize the base agent."""
        if llm is None:
            self.llm = get_default_llm(task_name=f"{self.__class__.__name__}_initialization")
            logger.info(f"[{self.__class__.__name__}] Initialized with default LLM model: {self.llm.model_name}")
        else:
            self.llm = llm
            logger.info(f"[{self.__class__.__name__}] Initialized with provided LLM model: {self.llm.model_name}")

        self.source_type = source_type
        # Get agent configuration based on source type
        self.config = get_agent_config(source_type=source_type)
        logger.info(f"[{self.__class__.__name__}] Initialized with source_type: {source_type}")
        logger.info(f"[{self.__class__.__name__}] Agent config: multi_collection_search_limit={self.config.multi_collection_search_limit}, " +
                   f"single_collection_search_limit={self.config.single_collection_search_limit}")

    @abstractmethod
    async def retrieve_documents(self, state: AgentState) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents based on the query and agent-specific criteria.
        
        Args:
            state: The current agent state with query and context
            
        Returns:
            List of retrieved documents
        """
        pass
    
    def process_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process retrieved documents to standardize format and extract metadata.
        Child classes can override this method for source-specific processing.
        
        Args:
            documents: The raw retrieved documents
            
        Returns:
            Processed documents
        """
        return process_retrieved_documents(documents, self.source_type)
    
    def format_documents_for_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        Format documents for the context prompt.
        Child classes can override this method for source-specific formatting.
        
        Args:
            documents: The processed documents
            
        Returns:
            Formatted document text for the LLM prompt
        """
        return format_documents_for_context(documents)
    
    def build_system_prompt(self) -> str:
        """
        Build the system prompt for the agent.
        Child classes should override this method for source-specific prompts.
        
        Returns:
            System prompt text
        """
        return f"""You are an AI assistant specialized in {self.source_type} data analysis. 
        Provide a comprehensive and detailed answer to the user's question based on the provided documents.
        Only use information from the documents. If the documents don't contain the answer, say so - don't make up information.
        Format your response clearly with markdown headers, bullet points, and tables where appropriate.
        """
    
    def build_human_prompt(
        self,
        question: str,
        context: str,
        current_query: Optional[str] = None,
        is_refined_query: bool = False,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build the human prompt including the question and context.
        
        Args:
            question: The original user question
            context: The formatted context/documents
            current_query: Optional refined query if different from original
            is_refined_query: Whether this is a refined query
            additional_context: Optional additional context
            
        Returns:
            Formatted human prompt
        """
        return build_human_prompt(
            question=question,
            context=context,
            current_query=current_query,
            is_refined_query=is_refined_query,
            additional_context=additional_context
        )
        
    async def generate_answer(self, state: AgentState) -> str:
        """
        Generate an answer based on the retrieved documents.
        This can be overridden by specialized agents for custom logic.
        """
        try:
            logger.info(f"[{self.__class__.__name__}.generate_answer] Generating answer from {len(state.retrieved_documents)} documents")
            
            # Format documents for the prompt
            formatted_docs = self.format_documents_for_context(state.retrieved_documents)
            
            # Get system prompt
            system_prompt = self.build_system_prompt()
            
            # Build human prompt
            # Check if we have additional context with a refined query flag
            is_refined_query = False
            current_query = state.current_query or state.question
            if hasattr(state, 'additional_context') and state.additional_context:
                is_refined_query = state.additional_context.get('refined_query', False)
            
            human_prompt = self.build_human_prompt(
                question=state.question,
                context=formatted_docs,
                current_query=current_query,
                is_refined_query=is_refined_query,
                additional_context=state.additional_context
            )
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(self.config.llm_request_delay)
            
            # Get the appropriate LLM for answer generation
            llm = get_answer_generation_llm()
            logger.info(f"[{self.__class__.__name__}.generate_answer] Using model: {llm.model_name}")

            response = await llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ]
            )
            
            logger.info(f"[{self.__class__.__name__}.generate_answer] Generated answer with model: {llm.model_name}")

            # Ensure we return a string (response.content could be a string or an object)
            if hasattr(response, 'content'):
                if isinstance(response.content, str):
                    return response.content
                else:
                    # Convert to string if not a string
                    return str(response.content)
            else:
                # Fallback if content not available
                return f"I analyzed {len(state.retrieved_documents)} documents but couldn't generate a proper response."
        
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}.generate_answer] Error generating answer: {e}")
            return f"I encountered an error while generating the answer: {str(e)}. Please try again or contact support if the issue persists."
        
    async def run_agent(
        self, 
        messages: List[Dict[str, Any]], 
        question: str,
        document_ids: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run the agent's full workflow from question to answer.
        
        Args:
            messages: List of previous messages in the conversation
            question: The user's current question or prompt
            document_ids: Optional list of specific document IDs to use
            topics: Optional list of topics for search
            keywords: Optional list of keywords for search
            additional_context: Optional additional context data
            
        Returns:
            The agent's response with answer and messages
        """
        logger.info(f"[{self.__class__.__name__}.run_agent] Processing question: '{question}'")
        
        # 1. Initialize agent state
        state = AgentState(
            question=question,
            document_ids=document_ids or [],
            topics=topics or [],
            keywords=keywords or [],
            additional_context=additional_context or {},
            chat_history=messages,
            source_type=self.source_type
        )
        
        # 2. Retrieve relevant documents
        state.retrieved_documents = await self.retrieve_documents(state)
        logger.info(f"[{self.__class__.__name__}.run_agent] Retrieved {len(state.retrieved_documents)} documents")
        
        # 3. Generate answer from documents
        answer = await self.generate_answer(state)
        logger.info(f"[{self.__class__.__name__}.run_agent] Generated answer")
        
        # 4. Format response
        response = self.format_response(answer, state.retrieved_documents)
        
        return response
    
    def format_response(self, answer: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format the agent's response for the chat interface."""
        response = {
            "messages": [
                {
                    "message_type": "ai",
                    "message_content": answer,
                    "message_id": f"ai_{int(time.time())}",
                    "message_extra": {}
                }
            ],
            "retrieved_documents": documents
        }
        
        return response 