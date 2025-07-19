import json
import asyncio
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.utils.postgresdb import PostgresDB
from app.config.settings import get_settings
from app.config.agent_config import get_agent_config
from app.agentic.base.base_agent import BaseAgent, AgentState
from app.agentic.utils.document_processor import extract_insights_from_metadata, format_documents_for_context
from app.agentic.utils.prompt_builder import build_context_agent_system_prompt
from app.utils.logging_config import setup_agent_logger

# Set up logging using the centralized configuration
logger = setup_agent_logger("ContextAgent")

class ContextAgentState(AgentState):
    """Extended state for Context-specific processing."""
    source_type: str = "context"  # Always set to context for this agent

class ContextAgent(BaseAgent):
    """
    Agent specialized for retrieving and processing specific document contexts
    based on document IDs. This agent uses PostgreSQL to retrieve documents
    instead of ChromaDB.
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the context agent."""
        super().__init__(llm=llm, source_type="context")
        settings = get_settings()
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.config = get_agent_config(source_type="context")
        self.postgres_db = PostgresDB()
        self.llm_request_delay = 0.5  # Delay to avoid rate limiting
    
    async def retrieve_documents(self, state: AgentState) -> List[Dict[str, Any]]:
        """
        Retrieve documents by their IDs from PostgreSQL.
        
        Args:
            state: The agent state containing document IDs
            
        Returns:
            List of retrieved documents
        """
        logger.info(f"[retrieve_documents] Processing document IDs: {state.document_ids}")
        
        if not state.document_ids:
            logger.warning("[retrieve_documents] No document IDs provided")
            return []
        
        # Use the existing method to retrieve documents by IDs
        return await self._retrieve_documents_by_ids(state.document_ids)
    
    async def _retrieve_documents_by_ids(self, document_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve documents from PostgreSQL by their IDs.
        
        Args:
            document_ids: List of document IDs to retrieve
            
        Returns:
            List of document dictionaries
        """
        logger.info(f"[_retrieve_documents_by_ids] Retrieving {len(document_ids)} documents")
        
        documents = []
        for doc_id in document_ids:
            try:
                # Retrieve document from PostgreSQL
                logger.info(f"[_retrieve_documents_by_ids] Retrieving document: {doc_id}")
                document = self.postgres_db.get_record("document_versions1", doc_id)
                
                if document:
                    logger.info(f"[_retrieve_documents_by_ids] Retrieved document: {doc_id}")
                    logger.info(f"[_retrieve_documents_by_ids] Document keys: {list(document.keys())}")
                    
                    # Check for json_metadata field
                    if 'json_metadata' in document:
                        logger.info(f"[_retrieve_documents_by_ids] Document has json_metadata field")
                        if isinstance(document['json_metadata'], str):
                            try:
                                parsed_json = json.loads(document['json_metadata'])
                                logger.info(f"[_retrieve_documents_by_ids] json_metadata is a string that was parsed to: {list(parsed_json.keys()) if isinstance(parsed_json, dict) else 'not a dict'}")
                            except json.JSONDecodeError:
                                logger.warning(f"[_retrieve_documents_by_ids] Failed to parse json_metadata as JSON")
                        elif isinstance(document['json_metadata'], dict):
                            logger.info(f"[_retrieve_documents_by_ids] json_metadata is already a dict with keys: {list(document['json_metadata'].keys())}")
                    
                    # Process the document to extract metadata using the utility function
                    processed_doc = extract_insights_from_metadata(document)
                    
                    # Add the document to the result list
                    documents.append(processed_doc)
                else:
                    logger.warning(f"[_retrieve_documents_by_ids] Document not found: {doc_id}")
            except Exception as e:
                logger.error(f"[_retrieve_documents_by_ids] Error retrieving document {doc_id}: {e}")
                logger.error(f"[_retrieve_documents_by_ids] Exception details: {str(e)}")
                import traceback
                logger.error(f"[_retrieve_documents_by_ids] Traceback: {traceback.format_exc()}")
        
        logger.info(f"[_retrieve_documents_by_ids] Retrieved {len(documents)} documents from PostgreSQL")
        return documents
    
    async def generate_answer(self, state: AgentState) -> str:
        """
        Generate an answer based on the retrieved documents.
        This method overrides the base implementation to provide context-specific processing.
        
        Args:
            state: Current agent state with retrieved documents
            
        Returns:
            Generated answer string
        """
        try:
            logger.info(f"[generate_answer] Generating answer from {len(state.retrieved_documents)} documents")
            
            if not state.retrieved_documents:
                return "I couldn't find any documents matching the specified IDs. Please check if the document IDs are correct."
            
            # Format documents for the prompt using the utility function
            formatted_docs = format_documents_for_context(state.retrieved_documents)
            
            # Construct system prompt using the utility function
            system_prompt = build_context_agent_system_prompt()
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(self.llm_request_delay)
            
            # Generate answer with LLM
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Question: {state.question}\n\nDocuments:\n{formatted_docs}")
                ]
            )
            
            # Extract content from response
            answer = response.content if hasattr(response, 'content') and isinstance(response.content, str) else str(response)
            
            logger.info(f"[generate_answer] Generated answer of length {len(answer)}")
            
            return answer
            
        except Exception as e:
            logger.error(f"[generate_answer] Error generating answer: {e}")
            return f"I encountered an error while analyzing the documents: {str(e)}. Please try again or contact support if the issue persists."
    
    # This method is kept for backwards compatibility
    async def process_context(self, question: str, document_ids: List[str]) -> Dict[str, Any]:
        """
        Process specific document contexts based on document IDs.
        This method is maintained for backwards compatibility with existing code.
        
        Args:
            question: The user's question
            document_ids: List of document IDs to retrieve and process
            
        Returns:
            Dictionary with messages in the standard format expected by parallel_workflow
        """
        logger.info(f"[process_context] Processing context for question: '{question}'")
        logger.info(f"[process_context] Document IDs: {document_ids}")
        
        # Create agent state
        state = ContextAgentState(
            question=question,
            document_ids=document_ids,
            source_type="context"
        )
        
        # Use the standard agent workflow to retrieve documents and generate answer
        state.retrieved_documents = await self.retrieve_documents(state)
        answer = await self.generate_answer(state)
        
        # Use the format_response method from BaseAgent class
        response = self.format_response(answer, state.retrieved_documents)
        
        # Log the response format for debugging
        logger.info(f"[process_context] Returning response with message_content length: {len(answer)}")
        
        return response