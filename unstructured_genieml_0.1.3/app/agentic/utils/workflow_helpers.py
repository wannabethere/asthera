"""
Workflow helper utilities shared across different workflow implementations.
"""

import json
import logging
import re
import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agentic.utils.prompt_builder import (
    build_document_analyst_prompt,
    build_query_refinement_prompt,
    build_results_aggregation_prompt
)

# Set up logging
logger = logging.getLogger("WorkflowHelpers")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def extract_answer_from_response(response: Dict[str, Any]) -> str:
    """
    Extract the answer text from an agent response.
    
    Args:
        response: The response from an agent
        
    Returns:
        The extracted answer text
    """
    if "messages" in response:
        for message in response["messages"]:
            if message.get("message_type") == "ai":
                return message.get("message_content", "")
    return ""

async def aggregate_results(
    question: str,
    sfdc_answer: str,
    gong_answer: str,
    llm: Optional[ChatOpenAI] = None,
    llm_request_delay: float = 0.3
) -> str:
    """
    Aggregate results from both data sources into a coherent response.
    
    Args:
        question: The user's question
        sfdc_answer: The answer from Salesforce agent
        gong_answer: The answer from Gong agent
        llm: Optional LLM to use, defaults to None (will create a new one)
        llm_request_delay: Delay before LLM request to avoid rate limiting
        
    Returns:
        Combined answer
    """
    system_prompt = build_results_aggregation_prompt()
    
    try:
        # Skip aggregation if one source is empty
        if not sfdc_answer:
            return gong_answer
        if not gong_answer:
            return sfdc_answer
        
        # Use provided LLM or create a new one
        if llm is None:
            llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # Add a small delay to avoid rate limiting
        await asyncio.sleep(llm_request_delay)
        
        # Generate aggregated answer
        aggregation_response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Question: {question}\n\nSalesforce Answer:\n{sfdc_answer}\n\nGong Answer:\n{gong_answer}\n\nPlease provide a synthesized answer:")
            ]
        )
        
        if isinstance(aggregation_response.content, str):
            return aggregation_response.content
        else:
            logger.warning("Aggregation response content is not a string")
            return f"Summary of Salesforce Data:\n{sfdc_answer}\n\nSummary of Gong Call Data:\n{gong_answer}"
        
    except Exception as e:
        logger.error(f"Error aggregating results: {e}")
        return f"Summary of Salesforce Data:\n{sfdc_answer}\n\nSummary of Gong Call Data:\n{gong_answer}"

async def analyze_document_relevance(
    state_data: Dict[str, Any],
    relevance_analysis_limit: int = 15,
    llm: Optional[ChatOpenAI] = None,
    llm_request_delay: float = 0.3
) -> Dict[str, Any]:
    """
    Analyze if retrieved documents are relevant to the question.
    
    Args:
        state_data: Dictionary with state data including question and retrieved documents
        relevance_analysis_limit: Maximum number of documents to analyze
        llm: Optional LLM to use, defaults to None (will create a new one)
        llm_request_delay: Delay before LLM request to avoid rate limiting
        
    Returns:
        Updated state data with analysis results
    """
    logger.info("[analyze_document_relevance] Analyzing document relevance")
    
    # Create a copy of the state data to avoid modifying the original
    updated_state = state_data.copy()
    
    # Get current date for temporal context
    current_date = datetime.now()
    current_date_formatted = current_date.strftime("%B %d, %Y")  # e.g., "June 15, 2023"
    
    # Use the prompt builder to get the system prompt
    system_prompt = build_document_analyst_prompt(current_date_formatted)
    
    # Prepare documents for analysis
    documents = updated_state.get("retrieved_documents", [])
    docs_for_analysis = documents[:min(len(documents), relevance_analysis_limit)]
    
    # Add date metadata when available to help with temporal analysis
    docs_with_dates = []
    for doc in docs_for_analysis[:10]:
        doc_with_date = {
            'content': doc.get('content', ''), 
            'type': doc.get('document_type', ''), 
            'relevance_score': doc.get('relevance_score', 0)
        }
        
        # Add date information if available
        metadata = doc.get('metadata', {})
        if 'date' in metadata:
            doc_with_date['date'] = metadata.get('date', '')
        elif 'gong_date' in doc:
            doc_with_date['date'] = doc.get('gong_date', '')
        elif 'created_date' in metadata:
            doc_with_date['date'] = metadata.get('created_date', '')
        
        docs_with_dates.append(doc_with_date)
    
    context = {
        "question": updated_state.get("question", ""),
        "current_query": updated_state.get("current_query", ""),
        "document_count": len(documents),
        "current_date": current_date_formatted,
        "samples": docs_with_dates
    }
    
    try:
        # Use provided LLM or create a new one
        if llm is None:
            llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # Add a small delay to avoid rate limiting
        await asyncio.sleep(llm_request_delay)
        
        analysis_response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Question: {updated_state.get('question', '')}\n\nAnalyze if these documents are sufficient:\n{json.dumps(context, indent=2)}")
            ]
        )
        
        if isinstance(analysis_response.content, str):
            json_match = re.search(r'{.*}', analysis_response.content, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
                updated_state["reflection"] = analysis.get("reasoning", "")
                
                # Check if documents are sufficient
                documents_sufficient = analysis.get("sufficient", False)
                updated_state["needs_refinement"] = not documents_sufficient
                
                logger.info(f"[analyze_document_relevance] Document sufficiency analysis: {documents_sufficient}")
                logger.info(f"[analyze_document_relevance] Needs refinement: {updated_state['needs_refinement']}")
                
                # Initialize additional_context if not present
                if "additional_context" not in updated_state:
                    updated_state["additional_context"] = {}
                
                # Store missing aspects and suggested search terms in state for refinement
                updated_state["additional_context"]["missing_aspects"] = analysis.get("missing_aspects", [])
                updated_state["additional_context"]["suggested_search_terms"] = analysis.get("suggested_search_terms", [])
                updated_state["additional_context"]["date_relevance"] = analysis.get("date_relevance", "")
                
                if updated_state["additional_context"]["missing_aspects"] or updated_state["additional_context"]["suggested_search_terms"]:
                    logger.info(f"[analyze_document_relevance] Missing aspects: {updated_state['additional_context']['missing_aspects']}")
                    logger.info(f"[analyze_document_relevance] Suggested search terms: {updated_state['additional_context']['suggested_search_terms']}")
                if updated_state["additional_context"]["date_relevance"]:
                    logger.info(f"[analyze_document_relevance] Date relevance: {updated_state['additional_context']['date_relevance']}")
                
                return updated_state
        
        # Fallback if analysis fails
        updated_state["reflection"] = "Could not properly analyze document sufficiency."
        updated_state["needs_refinement"] = (updated_state.get("query_type", "initial") == "initial")
        
    except Exception as e:
        logger.error(f"[analyze_document_relevance] Error analyzing relevance: {e}")
        updated_state["reflection"] = f"Error analyzing relevance: {e}"
        updated_state["needs_refinement"] = False
        
    return updated_state

async def refine_query(
    state_data: Dict[str, Any],
    llm: Optional[ChatOpenAI] = None,
    llm_request_delay: float = 0.3
) -> Dict[str, Any]:
    """
    Refine the search strategy to get more relevant documents.
    
    Args:
        state_data: Dictionary with state data
        llm: Optional LLM to use, defaults to None (will create a new one)
        llm_request_delay: Delay before LLM request to avoid rate limiting
        
    Returns:
        Updated state data with refined query
    """
    logger.info("[refine_query] Refining search strategy for better document retrieval")
    
    # Create a copy of the state data to avoid modifying the original
    updated_state = state_data.copy()
    
    # Store existing relevant documents to preserve them
    documents = updated_state.get("retrieved_documents", [])
    if documents:
        # Keep the top documents by relevance score
        sorted_docs = sorted(documents, key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Keep only documents with relevance score above threshold
        high_relevance_docs = [doc for doc in sorted_docs if doc.get('relevance_score', 0) >= 0.7]
        
        # If we have high relevance docs, save them as 'preserved_documents'
        if high_relevance_docs:
            # Ensure additional_context exists
            if "additional_context" not in updated_state:
                updated_state["additional_context"] = {}
                
            # Store up to 10 most relevant docs
            updated_state["additional_context"]["preserved_documents"] = high_relevance_docs[:10]
            logger.info(f"[refine_query] Preserving {len(updated_state['additional_context']['preserved_documents'])} highly relevant documents")
    
    # Get current date for temporal context
    current_date = datetime.now()
    current_date_formatted = current_date.strftime("%B %d, %Y")  # e.g., "June 15, 2023"
    
    # Use the prompt builder to get the system prompt
    system_prompt = build_query_refinement_prompt(current_date_formatted)
    
    # Ensure additional_context exists
    if "additional_context" not in updated_state:
        updated_state["additional_context"] = {}
    
    context = {
        "original_question": updated_state.get("question", ""),
        "previous_query": updated_state.get("current_query", ""),
        "reflection": updated_state.get("reflection", ""),
        "missing_aspects": updated_state.get("additional_context", {}).get("missing_aspects", []),
        "suggested_search_terms": updated_state.get("additional_context", {}).get("suggested_search_terms", []),
        "date_relevance": updated_state.get("additional_context", {}).get("date_relevance", ""),
        "current_date": current_date_formatted
    }
    
    try:
        # Use provided LLM or create a new one
        if llm is None:
            llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # Add a small delay to avoid rate limiting
        await asyncio.sleep(llm_request_delay)
        
        refinement_response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Here is the context:\n{json.dumps(context, indent=2)}\n\nPlease provide a refined search strategy.")
            ]
        )
        
        # Parse the response
        if isinstance(refinement_response.content, str):
            json_match = re.search(r'{.*}', refinement_response.content, re.DOTALL)
            if json_match:
                refinement = json.loads(json_match.group(0))
                
                # Update query and search terms
                updated_state["current_query"] = refinement.get("refined_query", updated_state.get("current_query", ""))
                updated_state["additional_context"]["additional_search_terms"] = refinement.get("additional_search_terms", [])
                updated_state["additional_context"]["refinement_explanation"] = refinement.get("explanation", "")
                updated_state["additional_context"]["time_period_focus"] = refinement.get("time_period_focus", "")
                
                # Set query type to refined
                updated_state["query_type"] = "refined"
                
                logger.info(f"[refine_query] Query refined to: {updated_state['current_query']}")
                logger.info(f"[refine_query] Additional search terms: {updated_state['additional_context']['additional_search_terms']}")
                if updated_state["additional_context"]["time_period_focus"]:
                    logger.info(f"[refine_query] Time period focus: {updated_state['additional_context']['time_period_focus']}")
                
                # Add any suggested terms to topics for better retrieval
                if updated_state["additional_context"]["additional_search_terms"]:
                    if "topics" not in updated_state or updated_state["topics"] is None:
                        updated_state["topics"] = []
                    updated_state["topics"].extend(updated_state["additional_context"]["additional_search_terms"])
                    
                # Increment recursion count
                updated_state["recursion_count"] = updated_state.get("recursion_count", 0) + 1
                
                return updated_state
        
        # If we couldn't parse the response, use a simpler approach
        updated_state["current_query"] = f"{updated_state.get('question', '')} {' '.join(updated_state.get('additional_context', {}).get('suggested_search_terms', []))}"
        updated_state["query_type"] = "refined"
        updated_state["recursion_count"] = updated_state.get("recursion_count", 0) + 1
        logger.info(f"[refine_query] Simple query refinement to: {updated_state['current_query']}")
        
    except Exception as e:
        logger.error(f"[refine_query] Error refining query: {e}")
        # If there's an error, just keep the current query
        
    return updated_state

def format_workflow_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format the workflow's response for the chat interface.
    
    Args:
        result: The workflow result containing the final answer
        
    Returns:
        Formatted response for the chat interface
    """
    import time
    
    # Extract the final answer
    final_answer = result.get("final_answer", "")
    if not final_answer:
        logger.warning("[format_workflow_response] final_answer is empty in the state!")
        final_answer = "I processed your request but couldn't generate a useful response. Please try again with a more specific question."
    
    # Create the response object with the final answer
    response = {
        "messages": [
            {
                "message_type": "ai",
                "message_content": final_answer,
                "message_id": f"ai_{int(time.time())}",
                "message_extra": {}
            }
        ]
    }
    
    # Log the final response content length
    logger.info(f"[format_workflow_response] Final response message_content length: {len(response['messages'][0]['message_content'])}")
    
    return response

async def determine_data_sources(
    question: str, 
    document_ids: Optional[List[str]] = None,
    logger: Optional[logging.Logger] = None
) -> str:
    """
    Determine which data sources to use based on the question and document IDs.
    
    Args:
        question: The user's question
        document_ids: Optional list of document IDs to use
        logger: Optional logger to use
        
    Returns:
        String indicating which data sources to use ("sfdc", "gong", "both", "context", or "csod")
    """
    if logger:
        logger.info(f"[determine_data_sources] Analyzing question: '{question}'")
        logger.info(f"[determine_data_sources] Document IDs: {document_ids}")
    
    # If document IDs are provided, use CONTEXT type
    if document_ids and len(document_ids) > 0:
        if logger:
            logger.info("[determine_data_sources] Document IDs provided, using 'context' data source")
        return "context"
    
    # Check if this is a Salesforce-specific query
    sfdc_keywords = ["opportunity", "deal", "pipeline", "forecast", "revenue", 
                    "salesforce", "sfdc", "account", "close date", "lead",
                    "activity", "task", "contact", "associate", "sales rep"]
    
    # Check if this is a Gong-specific query
    gong_keywords = ["call", "transcript", "conversation", "meeting", 
                    "objection", "pain point", "product feature", "competitor",
                    "talk time", "speaker", "recording", "gong"]
    
    # Check if this is a CSOD-specific query
    csod_keywords = ["csod", "cornerstone", "learning", "training", "course", 
                    "transcript", "organizational unit", "certification", "user",
                    "learning activity", "ou", "completion", "assignment"]
    
    # Count keyword matches for each source
    question_lower = question.lower()
    sfdc_matches = sum(1 for kw in sfdc_keywords if kw in question_lower)
    gong_matches = sum(1 for kw in gong_keywords if kw in question_lower)
    csod_matches = sum(1 for kw in csod_keywords if kw in question_lower)
    
    if logger:
        logger.info(f"[determine_data_sources] SFDC keyword matches: {sfdc_matches}")
        logger.info(f"[determine_data_sources] Gong keyword matches: {gong_matches}")
        logger.info(f"[determine_data_sources] CSOD keyword matches: {csod_matches}")
    
    # Apply logic for determining source
    if csod_matches > 0 and sfdc_matches == 0 and gong_matches == 0:
        # Only CSOD keywords found
        if logger:
            logger.info("[determine_data_sources] Using CSOD data source")
        return "csod"
    elif sfdc_matches > 0 and gong_matches == 0 and csod_matches == 0:
        # Only SFDC keywords found
        if logger:
            logger.info("[determine_data_sources] Using SFDC data source")
        return "sfdc"
    elif gong_matches > 0 and sfdc_matches == 0 and csod_matches == 0:
        # Only Gong keywords found
        if logger:
            logger.info("[determine_data_sources] Using Gong data source")
        return "gong"
    else:
        # Either multiple types of keywords found or none found
        if logger:
            logger.info("[determine_data_sources] Using both data sources")
        return "both"

def get_next_step_after_determination(data_source_type: str, logger: Optional[logging.Logger] = None) -> str:
    """
    Determine next step after data source determination.
    
    Args:
        data_source_type: Type of data source determined
        logger: Optional logger to use
        
    Returns:
        String indicating which node to go to next
    """
    if logger:
        logger.info(f"[get_next_step_after_determination] Data source type: {data_source_type}")
    
    # If we have specific document IDs, go directly to context processing
    if data_source_type == "context":
        if logger:
            logger.info("[get_next_step_after_determination] Using CONTEXT processing for document IDs")
        return "_process_context_node"
    
    # If we have a CSOD-specific query, go directly to CSOD processing
    if data_source_type == "csod":
        if logger:
            logger.info("[get_next_step_after_determination] Using CSOD processing")
        return "_process_csod_node"
    
    # Otherwise continue with the regular flow
    return "_retrieve_initial_documents_node"

def get_processor_node(data_source_type: str, logger: Optional[logging.Logger] = None) -> str:
    """
    Determine which processor node to use based on data source type.
    
    Args:
        data_source_type: Type of data source determined
        logger: Optional logger to use
        
    Returns:
        String indicating which processor node to use
    """
    if data_source_type == "sfdc":
        return "_process_sfdc_node"
    elif data_source_type == "gong":
        return "_process_gong_node"
    elif data_source_type == "csod":
        return "_process_csod_node"
    else:
        return "_process_both_node" 