import asyncio
import json
import logging
import re
from typing import Dict, List, Optional, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Set up logging
logger = logging.getLogger("smart_query_processor")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== Smart Query Processor Logger Initialized ===")

async def smart_query_processor(
    question: str, 
    document_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Process a query to determine source types and split into specialized queries.
    
    Args:
        question: User's original question
        document_ids: Optional list of document IDs
        
    Returns:
        Dictionary with processed query information
    """
    logger.info(f"[smart_query_processor] Processing question: '{question}'")
    logger.info(f"[smart_query_processor] Document IDs: {document_ids}")
    
    # If document IDs are provided, return "context" as source type
    if document_ids and len(document_ids) > 0:
        logger.info(f"[smart_query_processor] Document IDs provided, using 'context' source type")
        return {
            "source_type": "context",
            "original_query": question,
            "split_queries": {
                "context": question
            },
            "document_ids": document_ids
        }
    
    # If no document IDs, analyze the query for source type and topics
    try:
        # Initialize ChatOpenAI
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        # System prompt for analyzing the query
        system_prompt = """You are an expert at analyzing questions about sales and customer interactions.
        Determine if this question is about:
        1. Salesforce data (deals, pipeline, forecasts, opportunities)
        2. Gong call data (conversations, transcripts, what was said)
        3. Both Salesforce and Gong data

        Then reformulate the question into one or two specialized queries:
        - A Salesforce-specific query (if needed)
        - A Gong-specific query (if needed)

        Also extract key topics that should be searched for.

        Respond with a JSON in this format:
        {
            "source_type": "sfdc" | "gong" | "both",
            "split_queries": {
                "salesforce": "Salesforce-specific query" (if needed),
                "gong": "Gong-specific query" (if needed)
            },
            "topics": {
                "gong_topics": ["topic1", "topic2", ...],
                "salesforce_topics": ["topic1", "topic2", ...]
            }
        }
        
        IMPORTANT: Always use "sfdc" (not "salesforce") as the source_type value for Salesforce-related queries.
        """
        
        # Get the analysis from the LLM
        analysis_response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Question: {question}")
            ]
        )
        
        # Extract JSON from the response
        if isinstance(analysis_response.content, str):
            json_match = re.search(r'{.*}', analysis_response.content, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
                
                logger.info(f"[smart_query_processor] Analysis: {analysis}")
                
                # Add the original query
                analysis["original_query"] = question
                
                return analysis
        
        # If we couldn't extract JSON, return a default response
        logger.warning("[smart_query_processor] Couldn't extract JSON from LLM response")
        return {
            "source_type": "both",
            "original_query": question,
            "split_queries": {
                "salesforce": question,
                "gong": question
            },
            "topics": {
                "gong_topics": [],
                "salesforce_topics": []
            }
        }
        
    except Exception as e:
        logger.error(f"[smart_query_processor] Error processing query: {e}")
        # Return a default response in case of error
        return {
            "source_type": "both",
            "original_query": question,
            "split_queries": {
                "salesforce": question,
                "gong": question
            }
        } 