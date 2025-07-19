"""
Parallel workflow for coordinating specialized agentic.
"""

import logging
import time
import json
import asyncio
import copy
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
from app.utils.llm_factory import get_default_llm
from langgraph.graph import StateGraph, END

# Comment out unused agent imports
# from app.agentic.agents.salesforce_agent import SalesforceAgent
# from app.agentic.agents.gong_agent import GongAgent
from app.agentic.agents.context_agent import ContextAgent
from app.agentic.agents.csod_agent import CSODAgent
from app.agentic.agents.gong_agent import GongAgent
from app.agentic.agents.salesforce_agent import SalesforceAgent
from app.agentic.utils.workflow_helpers import (
    extract_answer_from_response,
    aggregate_results,
    analyze_document_relevance,
    refine_query,
    format_workflow_response,
    determine_data_sources,
    get_next_step_after_determination,
    get_processor_node
)

# Set up logging
logger = logging.getLogger("ParallelWorkflow")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== ParallelWorkflow Logger Initialized ===")

class DataSourceType(str, Enum):
    """Data source types for the parallel workflow."""
    # Comment out unused data source types
    # SFDC = "sfdc"
    # GONG = "gong"
    # BOTH = "both"
    CONTEXT = "context"  # For document ID-specific processing
    CSOD = "csod"  # Type for CSOD data

class QueryType(str, Enum):
    """Types of queries for refinement purposes."""
    INITIAL = "initial"
    REFINED = "refined"

class RetrievedDocument(BaseModel):
    """Document model with metadata and relevance score."""
    document_id: str
    document_type: str
    content: dict
    relevance_score: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    collection: str = Field(default="")

class ParallelWorkflowState(BaseModel):
    """State for the parallel workflow coordinator."""
    question: str
    original_question: str = ""
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    # Modify default data source type to CSOD
    data_source_type: DataSourceType = DataSourceType.CSOD
    current_query: str = ""
    query_type: QueryType = QueryType.INITIAL
    # Comment out unused answer fields
    # sfdc_answer: str = ""
    # gong_answer: str = ""
    csod_answer: str = ""
    final_answer: str = ""
    document_ids: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    specialized_queries: Dict[str, str] = Field(default_factory=dict)
    reflection: str = ""
    needs_refinement: bool = False
    recursion_count: int = Field(default=0)
    # Comment out unused filters
    # sfdc_filter: Optional[Dict[str, Any]] = None
    # gong_filter: Optional[Dict[str, Any]] = None
    csod_filter: Optional[Dict[str, Any]] = None
    # Document retrieval and ranking
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    selected_documents: List[RetrievedDocument] = Field(default_factory=list)
    section_keywords: List[str] = Field(default_factory=list)
    additional_context: Dict[str, Any] = Field(default_factory=dict)

class ParallelWorkflow:
    """
    Coordinator for parallel agent workflow.
    Manages specialized agentic for different data sources and combines their results.
    """

    def __init__(self, llm: Optional[get_default_llm] = None):
        """Initialize the parallel workflow coordinator."""
        self.llm = llm or get_default_llm(task_name="parallel_workflow")
        logger.info(f"[ParallelWorkflow] Using LLM model: {self.llm.model_name}")
        
        # Initialize only the CSOD agent
        # self.sfdc_agent = SalesforceAgent(llm=self.llm)
        # self.gong_agent = GongAgent(llm=self.llm)
        self.csod_agent = CSODAgent(llm=self.llm)
        
        # Configuration parameters for document handling
        self.max_recursion_limit = 2
        self.relevance_analysis_limit = 15
        self.max_selected_documents = 500  # Increased from 20 to 500 to match CSOD document limits
        self.llm_request_delay = 0.3
        
        # Initialize the workflow graph
        self.workflow = None
        self._init_workflow_graph()
    
    def _init_workflow_graph(self):
        """Initialize the workflow state graph with nodes and edges."""
        workflow = StateGraph(ParallelWorkflowState)
        
        # Define nodes - only include CSOD and context-related nodes
        workflow.add_node("_determine_data_sources_node", self._determine_data_sources_node)
        workflow.add_node("_retrieve_initial_documents_node", self._retrieve_initial_documents_node)
        # Comment out unused nodes
        # workflow.add_node("_process_sfdc_node", self._process_sfdc_node)
        # workflow.add_node("_process_gong_node", self._process_gong_node)
        # workflow.add_node("_process_both_node", self._process_both_node)
        workflow.add_node("_process_context_node", self._process_context_node)
        workflow.add_node("_process_csod_node", self._process_csod_node)
        workflow.add_node("_route_to_processing", self._route_to_processing)
        # workflow.add_node("_aggregate_results_node", self._aggregate_results_node)
        workflow.add_node("_check_and_refine_query", self._check_and_refine_query)
        workflow.add_node("_decide_after_processing", self._decide_after_processing)
        
        logger.info("[_init_workflow_graph] All nodes added to the workflow graph")
        
        # Start with determining data sources
        workflow.set_entry_point("_determine_data_sources_node")
        
        # Add conditional edge to determine next step after source determination
        workflow.add_conditional_edges(
            "_determine_data_sources_node",
            self._get_next_step_after_determination,
            {
                "_retrieve_initial_documents_node": "_retrieve_initial_documents_node",
                "_process_context_node": "_process_context_node",
                "_process_csod_node": "_process_csod_node"
            }
        )
        
        logger.info("[_init_workflow_graph] Added conditional edge from _determine_data_sources_node")
        
        # After retrieving documents, route to appropriate processor
        workflow.add_edge("_retrieve_initial_documents_node", "_route_to_processing")
        
        # Add conditional edges for routing to processors (only CSOD and context)
        workflow.add_conditional_edges(
            "_route_to_processing",
            self._get_processor_node,
            {
                # "_process_sfdc_node": "_process_sfdc_node",
                # "_process_gong_node": "_process_gong_node",
                # "_process_both_node": "_process_both_node",
                "_process_csod_node": "_process_csod_node"
            }
        )
        
        logger.info("[_init_workflow_graph] Added routing edges to appropriate processors")
        
        # Process results from each source type
        # workflow.add_edge("_process_sfdc_node", "_decide_after_processing")
        # workflow.add_edge("_process_gong_node", "_decide_after_processing")
        # workflow.add_edge("_process_both_node", "_aggregate_results_node")
        workflow.add_edge("_process_csod_node", "_check_and_refine_query")

        workflow.add_edge("_process_context_node", "_check_and_refine_query")

        logger.info("[_init_workflow_graph] Added edges from processor nodes to appropriate next steps")
        
        # After single-source processing, decide whether to refine or end
        workflow.add_conditional_edges(
            "_decide_after_processing",
            self._should_refine_query,
            {
                True: "_check_and_refine_query",  # Refine if needed
                False: END                       # Otherwise, end
            }
        )
        
        # Comment out the aggregation step since we're only using one agent
        # After aggregating both sources, go to refinement check
        # workflow.add_edge("_aggregate_results_node", "_check_and_refine_query")
        
        # After refinement check, either refine or end
        workflow.add_conditional_edges(
            "_check_and_refine_query",
            self._should_refine_query,
            {
                True: "_retrieve_initial_documents_node",  # Refine query and try again
                False: END  # Finish workflow
            }
        )
        
        logger.info("[_init_workflow_graph] Added final conditional edge from _check_and_refine_query")
        
        # Compile the graph
        self.workflow = workflow.compile()
        logger.info("[_init_workflow_graph] Workflow graph compiled successfully")
        return self.workflow
    
    async def run_workflow(
        self, 
        messages: List[Dict[str, Any]], 
        question: str,
        document_ids: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        priority: Optional[str] = None,
        specialized_queries: Optional[Dict[str, str]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run the workflow with the given messages and question.
        
        Args:
            messages: Previous conversation messages
            question: Current user question
            document_ids: Optional list of specific document IDs to use
            topics: Optional list of topics to focus on
            priority: Optional priority source type
            specialized_queries: Optional dictionary of specialized queries for each data source
            additional_context: Optional additional context for the workflow
            
        Returns:
            The workflow response
        """
        try:
            logger.info(f"[run_workflow] Messages: {messages}")
            start_time = time.time()
            logger.info("="*50)
            logger.info(f"PARALLEL WORKFLOW STARTED - Question: '{question}'")

            # Determine data source type from priority parameter
            # The priority is already determined by thread_handler.py using smart_query_processor
            if priority:
                source_type = priority
                logger.info(f"Using source type from priority: {priority}")
            else:
                # Fallback to "both" if no priority is provided
                source_type = "both"
                logger.info("No priority specified, defaulting to 'both' sources")
            
            # Map 'salesforce' to 'sfdc' for DataSourceType compatibility
            if source_type == "salesforce":
                source_type = "sfdc"
            elif source_type == "parallel":
                source_type = "both"
            
            # Use the topics that are already extracted and passed from thread_handler.py
            extracted_topics = list(topics) if topics else []
            logger.info(f"Using {len(extracted_topics)} topics passed from thread handler: {extracted_topics}")
            
            # Initialize workflow state
            state = ParallelWorkflowState(
                question=question,
                original_question=question,
                chat_history=messages,
                data_source_type=DataSourceType(source_type),
                current_query=question,
                document_ids=document_ids or [],
                topics=extracted_topics,
                specialized_queries=specialized_queries or {},
                additional_context=additional_context or {}
            )
            
            # If workflow graph is not initialized, initialize it
            if self.workflow is None:
                logger.info("Initializing workflow graph")
                self._init_workflow_graph()
            
            # If workflow still can't be initialized, fall back to non-graph implementation
            if self.workflow is None:
                logger.warning("Could not initialize workflow graph, falling back to non-graph implementation")
                result = await self._run_workflow_fallback(
                    messages=messages,
                    question=question,
                    document_ids=document_ids,
                    topics=extracted_topics,
                    priority=priority,
                    specialized_queries=specialized_queries,
                    additional_context=additional_context
                )
                
                return result
            
            # Run the workflow
            logger.info(f"Running workflow with data source type: {state.data_source_type}")
            result = await self.workflow.ainvoke(state)
            logger.info(f"Workflow execution completed in {time.time() - start_time:.2f} seconds")
            
            # Format the response
            response = self._format_response(result)
            logger.info("="*50)
            
            return response
            
        except Exception as e:
            logger.error(f"Error running workflow: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Return an error response
            return {
                "messages": [
                    {
                        "message_type": "ai",
                        "message_content": f"I encountered an error processing your question: {str(e)}. Please try again or rephrase your question.",
                        "message_id": f"error_{int(time.time())}",
                        "message_extra": {}
                    }
                ]
            }
    
    # Node implementations for LangGraph workflow
    # -----------------------------------------
    
    async def _determine_data_sources_node(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """Node implementation for determining data sources."""
        # If state already has a data source type from priority, use that
        if state.data_source_type != DataSourceType.CSOD:
            logger.info(f"Using predefined data source type: {state.data_source_type}")
            return state
            
        # Otherwise, determine based on question and document IDs
        data_source_type = await self._determine_data_sources(
            question=state.question, 
            document_ids=state.document_ids
        )
        state.data_source_type = data_source_type
        logger.info(f"Determined data source type from analysis: {state.data_source_type}")
        return state
    
    async def _determine_data_sources(self, question: str, document_ids: List[str] = None) -> DataSourceType:
        """
        Determine which data sources to use based on the question and document IDs.
        
        Args:
            question: The user's question
            document_ids: Optional list of specific document IDs
            
        Returns:
            DataSourceType indicating which source(s) to use
        """
        # If specific document IDs are provided, use context processing
        if document_ids and len(document_ids) > 0:
            logger.info(f"[_determine_data_sources] Using context processing for {len(document_ids)} document IDs")
            return DataSourceType.CONTEXT
        
        # Default to CSOD source type for this implementation
        logger.info("[_determine_data_sources] Defaulting to CSOD data source")
        return DataSourceType.CSOD
    
    def _get_next_step_after_determination(self, state: ParallelWorkflowState) -> str:
        """Determine next step after data source determination."""
        # Use the shared utility function
        return get_next_step_after_determination(state.data_source_type.value.lower(), logger)
    
    async def _retrieve_initial_documents_node(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """Node implementation for document retrieval."""
        # Call existing implementation with the appropriate source type
        if state.data_source_type == DataSourceType.CSOD:
            return await self._retrieve_initial_documents(state, "csod")
        else:
            return await self._retrieve_initial_documents(state, "both")
    
    async def _route_to_processing(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """Simple passthrough node for routing."""
        return state
    
    def _get_processor_node(self, state: ParallelWorkflowState) -> str:
        """Determine which processor node to use based on data source type."""
        # Extend the existing function logic to include CSOD
        if state.data_source_type == DataSourceType.CSOD:
            return "_process_csod_node"
        # Otherwise use the shared utility function
        return get_processor_node(state.data_source_type.value.lower())
    
    async def _process_context_node(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """
        Process specific document contexts using the context_agent.
        This node is called when specific document IDs are provided.
        
        Args:
            state: Current workflow state with document_ids
            
        Returns:
            Updated state with context processing results
        """
        logger.info("[_process_context_node] Processing with context agent")
        
        # Initialize the context agent
        context_agent = ContextAgent(llm=self.llm)
        
        # Process the documents using the context agent
        try:
            context_response = await context_agent.process_context(
                question=state.question,
                document_ids=state.document_ids
            )
            
            logger.info(f"[_process_context_node] Context agent response keys: {context_response.keys() if isinstance(context_response, dict) else 'not a dict'}")
            
            # Extract answer from context agent response
            if isinstance(context_response, dict) and "messages" in context_response:
                # Extract answer using the standard method
                answer = self._extract_answer_from_response(context_response)
                if answer:
                    state.final_answer = answer
                    logger.info(f"[_process_context_node] Extracted answer from messages, length: {len(state.final_answer)}")
                else:
                    # If extraction fails, provide a fallback message
                    logger.warning("[_process_context_node] Failed to extract answer from context agent response")
                    state.final_answer = "I processed the specified documents but couldn't generate a useful response. Please try with different document IDs or a reformulated question."
                
                # Also store any retrieved documents for reference if they're included
                if "retrieved_documents" in context_response:
                    retrieved_docs = context_response["retrieved_documents"]
                    state.retrieved_documents = retrieved_docs
                    
                    # Convert retrieved documents to selected_documents format if needed
                    if retrieved_docs and not state.selected_documents:
                        state.selected_documents = self._convert_to_selected_documents(retrieved_docs)
            else:
                # Handle unexpected response format
                logger.warning(f"[_process_context_node] Unexpected response format from context agent: {type(context_response)}")
                state.final_answer = "I encountered an issue processing the document contexts. Please try again with different document IDs."
            
            # If after all this, the answer is still empty, use a fallback
            if not state.final_answer:
                logger.warning("[_process_context_node] Empty answer from context agent")
                state.final_answer = "I processed the specified documents but couldn't generate a useful response. Please try with different document IDs or a reformulated question."
            
            logger.info(f"[_process_context_node] Context agent processing complete, final answer length: {len(state.final_answer)}")
            
        except Exception as e:
            logger.error(f"[_process_context_node] Error processing with context agent: {e}")
            import traceback
            logger.error(f"[_process_context_node] Traceback: {traceback.format_exc()}")
            
            # Set a fallback answer
            state.final_answer = f"I encountered an error while retrieving specific document context: {str(e)}. Please try again or provide a more general question."
        
        return state

    def _convert_to_selected_documents(self, documents: List[Dict[str, Any]]) -> List[RetrievedDocument]:
        """Convert raw document dictionaries to RetrievedDocument objects."""
        selected_docs = []
        
        for doc in documents:
            # Extract required fields
            doc_id = doc.get("document_id", "unknown")
            doc_type = doc.get("document_type", "unknown")
            content = doc.get("content", {})
            relevance = doc.get("relevance_score", 0.0)
            metadata = doc.get("metadata", {})
            collection = doc.get("collection", "")
            
            # Format content as dict if it's a string
            if isinstance(content, str):
                content = {"text": content}
            
            # Create RetrievedDocument object
            retrieved_doc = RetrievedDocument(
                document_id=doc_id,
                document_type=doc_type,
                content=content,
                relevance_score=relevance,
                metadata=metadata,
                collection=collection
            )
            
            selected_docs.append(retrieved_doc)
        
        return selected_docs

    async def _decide_after_processing(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """
        Decision node to determine if we should end the workflow or proceed to refinement.
        If a final answer is already generated, we end. Otherwise, we check for refinement.
        """
        if state.final_answer:
            logger.info("[_decide_after_processing] Final answer found, ending workflow.")
            # This state will cause _should_refine_query to return False
            state.needs_refinement = False
        else:
            logger.info("[_decide_after_processing] No final answer, proceeding to refinement check.")
            # This state will cause _should_refine_query to proceed with refinement logic
            state.needs_refinement = True # Or let the check decide
            
        return state

    async def _process_csod_node(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """Node implementation for processing CSOD data."""
        logger.info("[_process_csod_node] Processing CSOD data")
        
        try:
            # Create instance of the CSOD agent if not already initialized
            if not hasattr(self, 'csod_agent') or self.csod_agent is None:
                self.csod_agent = CSODAgent(llm=self.llm)
            
            # Determine which query to use (original or refined)
            query_to_use = state.current_query if state.current_query else state.question
            original_question = state.original_question if state.original_question else state.question
            
            # Add refinement info to additional context
            additional_context = state.additional_context or {}
            if state.query_type == QueryType.REFINED:
                additional_context['refined_query'] = True
                additional_context['original_question'] = original_question
                logger.info(f"[_process_csod_node] Using refined query: '{query_to_use}' (original: '{original_question}')")
            else:
                logger.info(f"[_process_csod_node] Using original query: '{query_to_use}'")
            
            # Run the CSOD agent
            csod_response = await self.csod_agent.run_agent(
                messages=state.chat_history,
                question=query_to_use,
                document_ids=state.document_ids,
                topics=state.topics,
                additional_context=additional_context
            )
            
            # Extract answer and documents
            state.csod_answer = self._extract_answer_from_response(csod_response)
            state.final_answer = state.csod_answer  # Set final answer directly for CSOD
            state.retrieved_documents = csod_response.get("retrieved_documents", [])
            logger.info(f"[_process_csod_node] CSOD agent returned {len(state.retrieved_documents)} documents")
            
            return state
            
        except Exception as e:
            logger.error(f"[_process_csod_node] Error processing CSOD data: {e}")
            import traceback
            logger.error(f"[_process_csod_node] Traceback: {traceback.format_exc()}")
            
            # Set default answer if processing fails
            state.csod_answer = f"I encountered an error processing CSOD data: {str(e)}. Please try again or contact support."
            state.final_answer = state.csod_answer
            
            return state

    async def _check_and_refine_query(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """
        Check if query refinement is needed and refine if necessary.
        This method now properly integrates with the CSOD agent's document sufficiency analysis.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with possibly refined query
        """
        logger.info("[_check_and_refine_query] Checking if query refinement is needed")
        
        # Skip refinement if specific document IDs are provided
        if state.document_ids:
            logger.info("[_check_and_refine_query] Specific document IDs provided, skipping refinement")
            return state
        
        # Skip if recursion limit reached
        if state.recursion_count >= self.max_recursion_limit:
            logger.info(f"[_check_and_refine_query] Reached recursion limit ({state.recursion_count}/{self.max_recursion_limit}), skipping refinement")
            return state
            
        # Initialize original_question if not set
        if not state.original_question:
            state.original_question = state.question
            
        # Initialize current_query if not set
        if not state.current_query:
            state.current_query = state.question
        
        # For CSOD data source, use the CSOD agent's document sufficiency analysis
        if state.data_source_type == DataSourceType.CSOD:
            # Create the CSOD agent if needed
            if not hasattr(self, 'csod_agent') or self.csod_agent is None:
                self.csod_agent = CSODAgent(llm=self.llm)
                
            # Check if we have documents to analyze
            if not state.retrieved_documents:
                # Retrieve initial documents for analysis
                state = await self._retrieve_initial_documents(state, "csod")
                
                # Use analyze_document_sufficiency directly from CSOD agent
                try:
                    # Run document retrieval (lightweight version just to get documents)
                    logger.info(f"[_check_and_refine_query] Retrieving initial documents for analysis")
                    
                    # Get current documents
                    from app.agentic.base.base_agent import AgentState
                    agent_state = AgentState(
                        question=state.current_query,
                        topics=state.topics,
                        document_ids=state.document_ids
                    )
                    
                    # Retrieve documents with the CSOD agent
                    retrieved_docs = await self.csod_agent.retrieve_documents(agent_state)
                    
                    # Store the retrieved documents in the state
                    state.retrieved_documents = retrieved_docs
                    logger.info(f"[_check_and_refine_query] Retrieved {len(retrieved_docs)} documents for analysis")
                    
                    # Analyze document sufficiency
                    if retrieved_docs:
                        logger.info(f"[_check_and_refine_query] Analyzing sufficiency of {len(retrieved_docs)} documents")
                        
                        # Use the CSOD agent's analyze_document_sufficiency method
                        sufficiency_analysis = await self.csod_agent.analyze_document_sufficiency(
                            question=state.current_query,
                            documents=retrieved_docs,
                            original_question=state.original_question
                        )
                        
                        # Update state based on analysis
                        state.needs_refinement = not sufficiency_analysis.get('sufficient', True)
                        state.reflection = sufficiency_analysis.get('reasoning', '')
                        
                        # Store suggested search terms in additional context
                        if not state.additional_context:
                            state.additional_context = {}
                            
                        state.additional_context['missing_aspects'] = sufficiency_analysis.get('missing_aspects', [])
                        state.additional_context['suggested_search_terms'] = sufficiency_analysis.get('suggested_search_terms', [])
                        state.additional_context['sufficiency_confidence'] = sufficiency_analysis.get('confidence', 0.5)
                        
                        # Log the analysis results
                        logger.info(f"[_check_and_refine_query] Document sufficiency analysis: {not state.needs_refinement}")
                        logger.info(f"[_check_and_refine_query] Reasoning: {state.reflection}")
                        logger.info(f"[_check_and_refine_query] Missing aspects: {state.additional_context['missing_aspects']}")
                        logger.info(f"[_check_and_refine_query] Suggested search terms: {state.additional_context['suggested_search_terms']}")
                        
                except Exception as e:
                    logger.error(f"[_check_and_refine_query] Error during document sufficiency analysis: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Default to no refinement on error
                    state.needs_refinement = False
            
            # Refine the query if needed
            if state.needs_refinement and state.recursion_count < self.max_recursion_limit:
                logger.info(f"[_check_and_refine_query] Documents not sufficient, refining query (iteration {state.recursion_count + 1})")
                
                try:
                    # Refine query using the CSOD agent's refine_query method
                    refined_query = await self.csod_agent.refine_query(
                        question=state.current_query,
                        original_question=state.original_question,
                        analysis={
                            'missing_aspects': state.additional_context.get('missing_aspects', []),
                            'suggested_search_terms': state.additional_context.get('suggested_search_terms', [])
                        }
                    )
                    
                    # Update state with refined query
                    if refined_query and refined_query != state.current_query:
                        # Set the refined query
                        state.current_query = refined_query
                        state.query_type = QueryType.REFINED
                        state.recursion_count += 1
                        
                        # Add refinement info to additional context
                        state.additional_context['refined_query'] = True
                        state.additional_context['refinement_iteration'] = state.recursion_count
                        
                        logger.info(f"[_check_and_refine_query] Query refined to: '{state.current_query}'")
                        
                        # Clear retrieved documents to force a new retrieval with the refined query
                        state.retrieved_documents = []
                    else:
                        logger.info(f"[_check_and_refine_query] No significant refinement produced, using original query")
                        
                except Exception as e:
                    logger.error(f"[_check_and_refine_query] Error refining query: {e}")
                    # Continue with original query on error
            
        else:
            # For other data sources, use the shared utility approach
            # Retrieve initial documents for analysis
            state = await self._retrieve_initial_documents(state, state.data_source_type.value.lower())
            
            # Analyze document relevance
            state = await self._analyze_document_relevance(state)
            
            # Check if refinement is needed
            if self._should_refine_query(state):
                logger.info("[_check_and_refine_query] Documents not sufficient, refining query")
                
                # Store original question before refinement if this is the first refinement
                if state.query_type == QueryType.INITIAL:
                    state.original_question = state.question
                
                # Refine the query
                state = await self._refine_query(state)
                
                # Retrieve with refined query
                state = await self._retrieve_initial_documents(state, state.data_source_type.value.lower())
                
                # Second analysis to check if refinement helped
                state = await self._analyze_document_relevance(state)
                
                # Add refinement info to additional_context for the agentic
                if not state.additional_context:
                    state.additional_context = {}
                    
                state.additional_context['refined_query'] = True
        
        return state
    
    async def _retrieve_initial_documents(self, state: ParallelWorkflowState, source_type: str) -> ParallelWorkflowState:
        """
        Retrieve initial documents or additional documents for refinement.
        When refining, this preserves existing relevant documents and adds new ones.
        
        Args:
            state: Current workflow state
            source_type: Type of source to retrieve from ("sfdc", "gong", or "both")
            
        Returns:
            Updated state with retrieved documents
        """
        logger.info(f"[_retrieve_initial_documents] Preparing topics and keywords for source: {source_type}")
        
        # This node no longer retrieves documents. It only prepares the state with topics/keywords.
        # The specialized agents are responsible for their own retrieval.
            
        # Prepare topics and keywords
        topics = list(state.topics)
        keywords = list(state.keywords)
        section_keywords = list(state.section_keywords)
            
        # Add default topics based on source type, but only if no specific topics exist
        if source_type in ["sfdc", "both"] and not topics:
                sfdc_topics = ["opportunity", "deal", "pipeline", "forecast", "revenue", "account"]
                sfdc_keywords = ["close date", "amount", "stage", "probability", "win", "lost"]
                for topic in sfdc_topics:
                    if topic not in topics:
                        topics.append(topic)
                for keyword in sfdc_keywords:
                    if keyword not in keywords:
                        keywords.append(keyword)
                    
        if source_type in ["gong", "both"] and not topics:
                gong_topics = ["call", "transcript", "objection", "pain_point", "feature", "action_item"]
                gong_keywords = ["meeting", "conversation", "customer", "product", "objection", "feature"]
                gong_section_keywords = ["Customer Pain Points", "Product Features", "Objections", 
                                      "Action Items", "Competitors", "Decision Criteria", 
                                      "Use Cases", "Deal Stage", "Buyer Roles"]
                
                for topic in gong_topics:
                    if topic not in topics:
                        topics.append(topic)
                for keyword in gong_keywords:
                    if keyword not in keywords:
                        keywords.append(keyword)
                for section in gong_section_keywords:
                    if section not in section_keywords:
                        section_keywords.append(section)
        elif source_type in ["gong", "both"] and topics:
            # If we have specific topics, only add section keywords for filtering
            # without overriding the actual query topics
            gong_section_keywords = ["Customer Pain Points", "Product Features", "Objections", 
                                  "Action Items", "Competitors", "Decision Criteria", 
                                  "Use Cases", "Deal Stage", "Buyer Roles"]
            
            # Important: These are section keywords for document organization purposes only,
            # NOT for replacing the query-specific topics
            for section in gong_section_keywords:
                if section not in section_keywords:
                    section_keywords.append(section)
            
            # Log that we're respecting the query-specific topics
            logger.info(f"[_retrieve_initial_documents] Using {len(topics)} specific topics from query analysis: {topics}")
            logger.info(f"[_retrieve_initial_documents] Added {len(section_keywords)} section keywords for content organization only")
            
            # Add any additional search terms from refinement to keywords
            additional_search_terms = state.additional_context.get("additional_search_terms", [])
            if additional_search_terms:
                for term in additional_search_terms:
                    if term not in keywords:
                        keywords.append(term)
            
            # Update state with additional keywords and section keywords
            state.topics = topics
            state.keywords = keywords
            state.section_keywords = section_keywords
            
        # Ensure retrieved_documents is empty so agents perform their own retrieval.
        state.retrieved_documents = []
        
        logger.info(f"[_retrieve_initial_documents] State prepared for {source_type} agent.")
        return state
    
    async def _analyze_document_relevance(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """
        Analyze if retrieved documents are relevant to the question and filter out irrelevant ones.
        Uses a progressive refinement approach that keeps high-relevance documents while seeking more if needed.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with relevance analysis and filtered documents
        """
        # Use the shared utility function, converting state to dict and back
        state_dict = state.dict()
        
        updated_state_dict = await analyze_document_relevance(
            state_data=state_dict,
            relevance_analysis_limit=self.relevance_analysis_limit,
            llm=self.llm,
            llm_request_delay=self.llm_request_delay
        )
        
        # Update state with results from the utility function
        for key, value in updated_state_dict.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        return state
    
    async def _refine_query(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """
        Refine the search strategy to get more relevant documents.
        Instead of just reformulating the query, this also preserves existing relevant
        documents and adds new ones to fill in gaps.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with refined query and preserved relevant documents
        """
        # Store original question if this is the first refinement
        if not state.original_question:
            state.original_question = state.question
        
        # Increment recursion count to avoid excessive refinement
        state.recursion_count += 1
        
        # Set query type to refined
        state.query_type = QueryType.REFINED
        
        # Use the shared utility function, converting state to dict and back
        state_dict = state.dict()
        
        updated_state_dict = await refine_query(
            state_data=state_dict,
            llm=self.llm,
            llm_request_delay=self.llm_request_delay
        )
        
        # Update state with results from the utility function
        for key, value in updated_state_dict.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        # Log refinement details
        logger.info(f"[_refine_query] Original query: '{state.original_question}'")
        logger.info(f"[_refine_query] Refined query: '{state.current_query}'")
        logger.info(f"[_refine_query] Refinement iteration: {state.recursion_count}")
        
        return state
    
    def _extract_answer_from_response(self, response: Dict[str, Any]) -> str:
        """Extract the answer text from an agent response."""
        # Use the shared utility function
        return extract_answer_from_response(response)
    
    async def _aggregate_results(self, state: ParallelWorkflowState) -> str:
        """
        Aggregate results from both data sources into a coherent response.
        
        Args:
            state: Current workflow state with answers from both sources
            
        Returns:
            Combined answer
        """
        # Use the shared utility function
        return await aggregate_results(
            question=state.question,
            sfdc_answer=state.sfdc_answer,
            gong_answer=state.gong_answer,
            llm=self.llm,
            llm_request_delay=self.llm_request_delay
        )
    
    def _should_refine_query(self, state: ParallelWorkflowState) -> bool:
        """Determine if we should refine the query based on document relevance analysis."""
        logger.info("[_should_refine_query] Evaluating if query refinement is needed")
        
        # Skip refinement if specific document IDs are provided
        if state.document_ids:
            logger.info("[_should_refine_query] Specific document IDs provided, skipping refinement")
            return False
        
        # Remove the automatic skipping of refinement for CSOD
        # if state.data_source_type == DataSourceType.CSOD:
        #     logger.info("[_should_refine_query] Using CSOD processing, skipping refinement")
        #     return False
            
        # If we've already refined once and still don't have good results,
        # we should move on rather than cycling endlessly
        if state.query_type == QueryType.REFINED and state.recursion_count >= self.max_recursion_limit:
            logger.info(f"[_should_refine_query] Reached recursion limit ({state.recursion_count}), moving on")
            return False
        
        # Check if we need refinement based on the relevance analysis reflection
        needs_refinement = state.needs_refinement
        
        if needs_refinement:
            logger.info("[_should_refine_query] Document relevance analysis indicates refinement needed")
        else:
            logger.info("[_should_refine_query] Document relevance analysis indicates documents are relevant")
        
        return needs_refinement
    
    def _format_response(self, result: Union[ParallelWorkflowState, Dict[str, Any]]) -> Dict[str, Any]:
        """Format the workflow's response for the chat interface."""
        # Handle both state object and dict results
        if isinstance(result, ParallelWorkflowState):
            result_dict = result.dict()
            logger.info(f"[_format_response] Using final_answer from ParallelWorkflowState, length: {len(result.final_answer)}")
        elif isinstance(result, dict):
            result_dict = result
            logger.info(f"[_format_response] Using final_answer from dict, length: {len(result.get('final_answer', ''))}")
        else:
            # Fallback for unknown result type
            logger.warning(f"[_format_response] Unknown result type in _format_response: {type(result)}")
            result_dict = {"final_answer": "I processed your request but encountered an issue with the response format."}
        
        # Use the shared utility function
        return format_workflow_response(result_dict)

    async def _run_workflow_fallback(
        self, 
        messages: List[Dict[str, Any]], 
        question: str,
        document_ids: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        priority: Optional[str] = None,
        specialized_queries: Optional[Dict[str, str]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fallback implementation of the workflow without using LangGraph.
        Used when the graph workflow encounters errors.
        """
        logger.info("Using fallback workflow implementation")
        
        # 1. Determine data sources needed based on priority or analysis
        if priority:
            # Use the priority passed from thread_handler
            if priority == "gong":
                data_source_type = DataSourceType.CSOD
            elif priority == "salesforce":
                data_source_type = DataSourceType.CSOD
            else:  # "parallel" or any other value
                data_source_type = DataSourceType.CSOD
            logger.info(f"Using data source type from priority: {data_source_type}")
        else:
            # Fall back to the analysis method if no priority is provided
            data_source_type = await self._determine_data_sources(
                question=question, 
                document_ids=document_ids
            )
            logger.info(f"Determined data source type from analysis: {data_source_type}")
        
        # 2. Initialize workflow state
        state = ParallelWorkflowState(
            question=question,
            original_question=question,
            current_query=question,
            chat_history=messages,
            data_source_type=data_source_type,
            document_ids=document_ids or [],
            topics=topics or [],
            specialized_queries=specialized_queries or {},
            additional_context=additional_context or {}
        )
        
        # 3. Execute workflow based on data source type
        if data_source_type == DataSourceType.CSOD:
            # CSOD data only
            # First check if query refinement is needed
            state = await self._check_and_refine_query(state)
            
            # Process with CSOD agent, passing the possibly refined query
            csod_state = ParallelWorkflowState(
                question=state.question,
                original_question=state.original_question,
                current_query=state.current_query,  # Use possibly refined query
                chat_history=state.chat_history,
                data_source_type=state.data_source_type,
                document_ids=state.document_ids,
                topics=state.topics,
                additional_context=state.additional_context or {},
                recursion_count=state.recursion_count
            )
            
            csod_response = await self._process_csod_node(csod_state)
            state.csod_answer = csod_response.csod_answer
            state.final_answer = csod_response.final_answer
            state.retrieved_documents = csod_response.retrieved_documents
            
        # 4. Format the final response
        response = self._format_response(state)
        
        return response

    async def _process_context_node(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """
        Process specific document contexts using the context_agent.
        This node is called when specific document IDs are provided.

        Args:
            state: Current workflow state with document_ids

        Returns:
            Updated state with context processing results
        """
        logger.info("[_process_context_node] Processing with context agent")

        # Initialize the context agent
        context_agent = ContextAgent(llm=self.llm)

        # Process the documents using the context agent
        try:
            context_response = await context_agent.process_context(
                question=state.question,
                document_ids=state.document_ids
            )

            logger.info(f"[_process_context_node] Context agent response keys: {context_response.keys() if isinstance(context_response, dict) else 'not a dict'}")

            # Extract answer from context agent response
            if isinstance(context_response, dict) and "messages" in context_response:
                # Extract answer using the standard method
                answer = self._extract_answer_from_response(context_response)
                if answer:
                    state.final_answer = answer
                    logger.info(f"[_process_context_node] Extracted answer from messages, length: {len(state.final_answer)}")
                else:
                    # If extraction fails, provide a fallback message
                    logger.warning("[_process_context_node] Failed to extract answer from context agent response")
                    state.final_answer = "I processed the specified documents but couldn't generate a useful response. Please try with different document IDs or a reformulated question."

                # Also store any retrieved documents for reference if they're included
                if "retrieved_documents" in context_response:
                    retrieved_docs = context_response["retrieved_documents"]
                    state.retrieved_documents = retrieved_docs

                    # Convert retrieved documents to selected_documents format if needed
                    if retrieved_docs and not state.selected_documents:
                        state.selected_documents = self._convert_to_selected_documents(retrieved_docs)
            else:
                # Handle unexpected response format
                logger.warning(f"[_process_context_node] Unexpected response format from context agent: {type(context_response)}")
                state.final_answer = "I encountered an issue processing the document contexts. Please try again with different document IDs."

            # If after all this, the answer is still empty, use a fallback
            if not state.final_answer:
                logger.warning("[_process_context_node] Empty answer from context agent")
                state.final_answer = "I processed the specified documents but couldn't generate a useful response. Please try with different document IDs or a reformulated question."

            logger.info(f"[_process_context_node] Context agent processing complete, final answer length: {len(state.final_answer)}")

        except Exception as e:
            logger.error(f"[_process_context_node] Error processing with context agent: {e}")
            import traceback
            logger.error(f"[_process_context_node] Traceback: {traceback.format_exc()}")

            # Set a fallback answer
            state.final_answer = f"I encountered an error while retrieving specific document context: {str(e)}. Please try again or provide a more general question."

        return state

    def _convert_to_selected_documents(self, documents: List[Dict[str, Any]]) -> List[RetrievedDocument]:
        """Convert raw document dictionaries to RetrievedDocument objects."""
        selected_docs = []

        for doc in documents:
            # Extract required fields
            doc_id = doc.get("document_id", "unknown")
            doc_type = doc.get("document_type", "unknown")
            content = doc.get("content", {})
            relevance = doc.get("relevance_score", 0.0)
            metadata = doc.get("metadata", {})
            collection = doc.get("collection", "")

            # Format content as dict if it's a string
            if isinstance(content, str):
                content = {"text": content}

            # Create RetrievedDocument object
            retrieved_doc = RetrievedDocument(
                document_id=doc_id,
                document_type=doc_type,
                content=content,
                relevance_score=relevance,
                metadata=metadata,
                collection=collection
            )

            selected_docs.append(retrieved_doc)

        return selected_docs

    async def _decide_after_processing(self, state: ParallelWorkflowState) -> ParallelWorkflowState:
        """
        Decision node to determine if we should end the workflow or proceed to refinement.
        If a final answer is already generated, we end. Otherwise, we check for refinement.
        """
        if state.final_answer:
            logger.info("[_decide_after_processing] Final answer found, ending workflow.")
            # This state will cause _should_refine_query to return False
            state.needs_refinement = False
        else:
            logger.info("[_decide_after_processing] No final answer, proceeding to refinement check.")
            # This state will cause _should_refine_query to proceed with refinement logic
            state.needs_refinement = True # Or let the check decide

        return state

async def test_parallel_workflow():
    """Quick test function for the parallel workflow."""
    print("=" * 80)
    print("TESTING PARALLEL WORKFLOW")
    print("=" * 80)
    
    # Initialize the workflow
    workflow = ParallelWorkflow(llm=get_default_llm(task_name="parallel_workflow_test"))
    
    # Get user input for testing
    test_query = input("Enter a test query for the parallel workflow: ")
    
    print(f"\nProcessing query: '{test_query}'")
    start_time = time.time()
    
    # Run the workflow with the test query
    result = await workflow.run_workflow(
        messages=[],
        question=test_query
    )
    
    # Print processing time
    processing_time = time.time() - start_time
    print(f"\nProcessing completed in {processing_time:.2f} seconds")
    
    # Print the result
    if result and "messages" in result:
        for message in result["messages"]:
            if message.get("message_type") == "ai":
                print("\nResult:")
                print("-" * 40)
                print(message.get("message_content", ""))
                print("-" * 40)

if __name__ == "__main__":
    import asyncio
    
    # Run the test function
    asyncio.run(test_parallel_workflow()) 