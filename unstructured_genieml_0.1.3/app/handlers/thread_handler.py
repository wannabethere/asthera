from datetime import datetime
from typing import Any, Dict, List
import os
import logging
import json
import uuid
import time
from app.agentic.processing.query_splitter import smart_query_processor
from app.agentic.orchestration.parallel_workflow import ParallelWorkflow
# Comment out thread_utils import since we're not using PostgreSQL
# from app.utils import threads as thread_utils
from app.config.settings import get_settings
from app.utils.llm_factory import get_default_llm
from app.agentic.utils.sf_sql_translator import translate, execute_query_and_get_results
from app.services.database.connection_service import connection_service
# Import functions from functions_for_pipeline.py
from app.agentic.orchestration.functions_for_pipeline import create_agent

# Set up a dedicated logger for the thread handler
logger = logging.getLogger("ThreadHandler")
logger.setLevel(logging.DEBUG)
llm = get_default_llm(task_name="thread_handler", seed=42)
logger.info(f"[ThreadHandler] Using LLM model: {getattr(llm, 'model_name', 'unknown')}")

# Comment out Redis client and use in-memory storage instead
# redis_client = connection_service.redis_client
# In-memory thread storage as a replacement for Redis
in_memory_threads = {}

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== Thread Handler Logger Initialized ===")


def _is_summary_or_highlight_question(prompt: str) -> bool:
    """
    Detect if the question is asking for a summary or highlights.
    
    Args:
        prompt: The user's question/prompt
        
    Returns:
        bool: True if this is a summary/highlight question, False otherwise
    """
    prompt_lower = prompt.lower().strip()
    
    # Summary indicators
    summary_keywords = [
        'summary', 'summarize', 'summarise', 'sum up', 'overview', 'recap',
        'brief', 'outline', 'gist', 'main points', 'key points', 'takeaways',
        'what happened', 'what was discussed', 'what did they talk about',
        'give me a summary', 'can you summarize', 'provide a summary'
    ]
    
    # Highlight indicators  
    highlight_keywords = [
        'highlight', 'highlights', 'key highlights', 'main highlights',
        'important points', 'significant points', 'notable points',
        'what stood out', 'most important', 'key insights', 'top insights',
        'what were the highlights', 'show me the highlights'
    ]
    
    # General broad question indicators
    broad_keywords = [
        'tell me about', 'what about', 'everything about', 'all about',
        'general overview', 'broad overview', 'complete picture',
        'full picture', 'comprehensive view', 'overall view'
    ]
    
    all_keywords = summary_keywords + highlight_keywords + broad_keywords
    
    # Check if any of these keywords appear in the prompt
    for keyword in all_keywords:
        if keyword in prompt_lower:
            return True
    
    # Check for question patterns that typically ask for summaries
    summary_patterns = [
        'what was the call about',
        'what did they discuss',
        'what happened in the',
        'what was covered',
        'what topics were discussed',
        'what were they talking about',
        'give me an overview',
        'can you give me',
        'tell me what',
        'what can you tell me'
    ]
    
    for pattern in summary_patterns:
        if pattern in prompt_lower:
            return True
    
    return False


async def chat_with_documents(
    prompt: str,
    thread_id: str | None = None,
    return_new_messages_only: bool = True,
    document_ids: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Chat with documents - ask questions about processed documents

    Args:
        prompt: The user's prompt
        thread_id: Optional ID of an existing thread
        return_new_messages_only: Whether to only return new messages in the response
        document_ids: Optional list of specific document IDs to use

    Returns:
        dict: Response containing the agent's reply and thread_id
    """
    logger.info("="*50)
    logger.info(f"DOCUMENT CHAT INITIATED - Prompt: '{prompt}', Thread ID: {thread_id}")
    if document_ids:
        logger.info(f"Document IDs provided: {document_ids}")
    
    # Check if this is a pharma query
    if "@pharma" in prompt:
        logger.info("@pharma detected in query - routing to pharma specialized agent")
        return await handle_pharma_query(prompt, thread_id, return_new_messages_only)

    # Get API key from settings
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment")
        raise ValueError("OPENAI_API_KEY not found in environment")
        
    # Set environment variable directly to ensure it's picked up by OpenAI
    os.environ["OPENAI_API_KEY"] = api_key
    logger.info("OpenAI API key set in environment variables")
        
    # Initialize the SelfRAGDocumentChat agent with the OpenAI LLM
    logger.info("Initializing ChatOpenAI and SelfRAGDocumentChat")
    
    # Create new thread if no thread_id provided
    if not thread_id:
        # Generate UUID for thread ID (safe for concurrent users)
        thread_id = str(uuid.uuid4())
        # Initialize empty list for this thread in in-memory storage
        in_memory_threads[thread_id] = []
        logger.info(f"Created new thread in memory with ID: {thread_id}")
    else:
        logger.info(f"Using existing thread with ID: {thread_id}")
        # Verify that the thread exists in in-memory storage, or create it
        if thread_id not in in_memory_threads:
            logger.warning(f"Thread with ID {thread_id} not found in memory. Creating it.")
            in_memory_threads[thread_id] = []

    # Fetch existing messages in this thread from in-memory storage
    messages = in_memory_threads.get(thread_id, [])
    logger.info(f"Retrieved {len(messages)} messages from memory for thread {thread_id}")
    
    # Determine priority and topics
    priority = "csod"  # Default priority is now CSOD instead of parallel
    topics = []
    processed_prompt = prompt  # This will hold the final prompt to use
    
    # If document_ids are provided, bypass query processor and use "context" priority
    if document_ids and len(document_ids) > 0:
        logger.info("Document IDs provided - bypassing smart query processor and using 'context' priority")
        priority = "context"
    else:
        # Process query with smart query processor, including chat history for follow-up detection
        logger.info("Processing query with smart query processor including chat history")
        result_json = await smart_query_processor(prompt, chat_history=messages)
        logger.info(f"Query splitter result: {result_json}")
        
        # Check if this was a follow-up question and use the standalone version
        followup_analysis = result_json.get("followup_analysis", {})
        if followup_analysis.get("is_follow_up", False):
            processed_prompt = followup_analysis.get("standalone_question", prompt)
            logger.info(f"Follow-up question detected - using standalone version: '{processed_prompt}'")
            logger.info(f"Follow-up reasoning: {followup_analysis.get('reasoning', 'N/A')}")
        
        # Comment out old priority determination that used gong and salesforce
        # priority = result_json.get("priority", "parallel")  # Can be "gong", "salesforce", or "parallel"
        # logger.info(f"Query priority determined by splitter: '{priority}'")
        
        # Always use csod priority
        priority = "csod"
        logger.info(f"Using CSOD priority for all queries")
        
        # Extract topics for CSOD
        # Check if the result includes csod_topics, otherwise extract from the general topics
        if "topics" in result_json:
            # First check if we have dedicated CSOD topics
            if "csod_topics" in result_json["topics"]:
                topics = result_json["topics"].get("csod_topics", [])
                logger.info(f"Using {len(topics)} CSOD-specific topics from query analysis: {topics}")
            # Otherwise check if we have general topics we can use
            elif "topics" in result_json["topics"]:
                topics = result_json["topics"].get("topics", [])
                logger.info(f"Using {len(topics)} general topics from query analysis: {topics}")
            # As a fallback, use combined topics from other sources if available
            else:
                gong_topics = result_json["topics"].get("gong_topics", [])
                sfdc_topics = result_json["topics"].get("salesforce_topics", [])
                topics = list(set(gong_topics + sfdc_topics))
                logger.info(f"Using {len(topics)} combined topics from other sources: {topics}")
        else:
            # If no topics at all, use basic extraction
            csod_keywords = ["learning", "training", "course", "transcript", "user", "organizational unit"]
            topics = [word for word in processed_prompt.lower().split() if len(word) > 3]
            # Add CSOD keywords that might be relevant
            for keyword in csod_keywords:
                if keyword.lower() in processed_prompt.lower() and keyword not in topics:
                    topics.append(keyword)
            logger.info(f"Using {len(topics)} basic extracted topics for CSOD query: {topics}")
            
        # Also check if there's a refined query for CSOD
        if "csod_query" in result_json:
            processed_prompt = result_json["csod_query"]
            logger.info(f"Using CSOD-specific query from processor: '{processed_prompt}'")
        elif "standalone_question" in result_json:
            processed_prompt = result_json["standalone_question"]
            logger.info(f"Using standalone question as processed prompt: '{processed_prompt}'")
    
    # Determine config source for agent configuration
    config_source = "csod"  # Default to CSOD
    
    # Comment out unstructured and gong specific detection
    """
    if "@unstructured" in processed_prompt:
        logger.info("Detected @unstructured in prompt, using GENERIC document type with unfiltered search")
        # Remove the @unstructured tag from the prompt
        clean_prompt = processed_prompt.replace("@unstructured", "").strip()
        logger.info(f"Cleaned prompt: {clean_prompt}")
        
        # Check if the prompt mentions gong
        if "gong" in clean_prompt.lower():
            logger.info("Detected 'gong' in prompt, using GONG_TRANSCRIPT document type")
            config_source = "gong"  # Use gong config source
        
        # Use the cleaned prompt without the @unstructured tag
        processed_prompt = clean_prompt
    """
    
    # Use the app.agentic ParallelWorkflow implementation
    logger.info("Using app.agentic ParallelWorkflow")
    document_chat = ParallelWorkflow(llm=llm)
    
    # Run the agent with the processed prompt (potentially rephrased from follow-up)
    logger.info(f"Running ParallelWorkflow with processed prompt: '{processed_prompt}'")
    if document_ids:
        logger.info(f"Using specific document IDs: {document_ids}")
    
    # Check if this is a summary/highlight question (only if no document_ids)
    if not document_ids:
        is_summary_question = _is_summary_or_highlight_question(processed_prompt)
        if is_summary_question:
            logger.info("Detected summary/highlight question - skipping topic-based filtering for broader search")
            topics = []  # Clear topics to ensure broader search
        else:
            logger.info(f"Using topic-based filtering with {len(topics)} topics: {topics}")
    
    # Extract specialized queries from query_splitter result
    specialized_queries = {}
    # if 'result_json' in locals():
    #     specialized_queries = {
    #         "gong": result_json["split_queries"].get("gong", processed_prompt),
    #         "salesforce": result_json["split_queries"].get("salesforce", processed_prompt)
    #     }
    # else:
    #     # If no query processing happened (e.g., document_ids provided), use the original prompt
    #     specialized_queries = {
    #         "gong": processed_prompt,
    #         "salesforce": processed_prompt
    #     }

    # Add SQL translation step for parallel mode
    additional_context = {}
    if priority == "parallel" and "salesforce" in specialized_queries:
        try:
            logger.info("Parallel mode detected - running SQL translation for Salesforce query")

            # Get the specialized Salesforce query
            sf_query = specialized_queries["salesforce"]
            logger.info(f"Translating Salesforce query to SQL: '{sf_query}'")

            # Translate the natural language query to SQL
            sql = translate(sf_query)
            logger.info(f"Generated SQL query: {sql}")

            # Execute the SQL query and get results
            sql_results = execute_query_and_get_results(sql)
            logger.info(f"SQL query returned {len(sql_results)} results")

            if sql_results:
                # Extract opportunity names for cross-referencing
                opportunity_names = [row.get("name") for row in sql_results if row.get("name")]
                logger.info(f"Extracted {len(opportunity_names)} opportunity names: {opportunity_names[:5]}...")

                # Add SQL results to additional context for the agents
                additional_context = {
                    "sql_results": sql_results,
                    "opportunity_names": opportunity_names
                }
                logger.info(f"Successfully added SQL results to additional_context: {len(sql_results)} results, {len(opportunity_names)} names")
            else:
                logger.warning("SQL query executed but returned no results")
                additional_context = {}

        except Exception as e:
            logger.error(f"Error in SQL translation: {e}")
            import traceback
            logger.error(f"SQL translation traceback: {traceback.format_exc()}")
            logger.info("Continuing with standard parallel workflow")
            additional_context = {}

    # Call run_workflow with the correct parameters and additional context
    response = await document_chat.run_workflow(
        messages=messages,
        question=processed_prompt,
        document_ids=document_ids,
        topics=topics,
        priority=priority,
        specialized_queries=specialized_queries,
        additional_context=additional_context  # Add the SQL results
    )
    
    logger.info(f"ParallelWorkflow execution completed")
    logger.info(f"ParallelWorkflow response keys: {response.keys() if hasattr(response, 'keys') else 'No keys'}")
    
    # Get new AI messages from raw workflow response before formatting
    # This is the single source of truth for what's new in this turn.
    new_messages = _get_new_messages(response["messages"], messages)
    
    # Create human message for the current prompt to be stored in history
    human_message = {
        "message_id": str(uuid.uuid4()),
        "message_type": "human",
        "message_content": prompt,
        "message_extra": {},
        "created_at": datetime.now().isoformat()
    }

    # Save messages to in-memory storage
    logger.info("Saving new messages to memory")
    # Get the current thread history
    current_thread_history = in_memory_threads.get(thread_id, [])
    # Add new messages
    current_thread_history.extend(new_messages)
    # Update the thread history
    in_memory_threads[thread_id] = current_thread_history

    if 'messages' in response:
        message_sample = response['messages'][0] if response['messages'] else 'No messages'
        logger.info(f"Messages structure sample: {json.dumps(message_sample)[:200]}...")
    else:
        logger.warning("No 'messages' key in ParallelWorkflow response")

    # Determine which messages to format and return based on the request
    messages_to_return = []
    if return_new_messages_only:
        logger.info("Returning only new messages")
        messages_to_return = new_messages
    else:
        logger.info("Returning all messages in the thread")
        messages_to_return = current_thread_history

    # Prep response for API
    response["thread_id"] = thread_id
    response["messages"] = _convert_message_format(messages_to_return)
    logger.info(f"Final response prepared with {len(response['messages'])} messages")
    logger.info("="*50)
    
    return response


def get_all_threads(limit: int = -1) -> List[Dict]:
    """
    Get all threads from in-memory storage
    """
    # Return a list of thread objects from in-memory storage
    threads = []
    for thread_id, messages in in_memory_threads.items():
        # Create a simple thread object with the thread_id as both id and name
        threads.append({
            "id": thread_id,
            "name": f"Thread {thread_id}",
            "created_at": messages[0]["created_at"] if messages else datetime.now().isoformat()
        })

    # Apply limit if specified
    if limit > 0:
        threads = threads[:limit]

    return threads


def get_thread(thread_id: str) -> Dict:
    """
    Get a thread by ID from in-memory storage
    """
    if thread_id not in in_memory_threads:
        return {
            "id": None,
            "name": "Thread not found",
            "messages": []
        }
    
    messages = in_memory_threads.get(thread_id, [])
    response = {
        "id": thread_id,
        "name": f"Thread {thread_id}",
        "messages": _convert_message_format(messages),
    }
    return response


def _get_new_messages(
    agent_response: List[Dict[str, Any]], existing_messages: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Return only new messages from the agent's response
    """
    new_messages = []
    for msg in agent_response:
        if msg["message_id"] not in [m["message_id"] for m in existing_messages]:
            new_messages.append(msg)
    return new_messages


def _convert_message_format(messages):
    formatted = []
    for msg in messages:
        content = msg["message_content"]
        if not isinstance(content, str):
            content = json.dumps(content)
        formatted.append({
            "role": msg["message_type"],
            "content": content,
            "id": msg.get("message_id"),
        })
    return formatted


async def handle_pharma_query(
    prompt: str,
    thread_id: str | None = None,
    return_new_messages_only: bool = True,
) -> Dict[str, Any]:
    """
    Handle pharma-specific queries using the functions_for_pipeline module

    Args:
        prompt: The user's prompt (containing @pharma)
        thread_id: Optional ID of an existing thread
        return_new_messages_only: Whether to only return new messages in the response

    Returns:
        dict: Response containing the agent's reply and thread_id
    """
    logger.info("="*50)
    logger.info(f"PHARMA QUERY HANDLER - Prompt: '{prompt}', Thread ID: {thread_id}")

    # Remove the @pharma tag from the prompt
    clean_prompt = prompt.replace("@pharma", "").strip()
    logger.info(f"Cleaned prompt for pharma agent: '{clean_prompt}'")

    # Create new thread if no thread_id provided
    if not thread_id:
        thread_id = str(uuid.uuid4())
        in_memory_threads[thread_id] = []
        logger.info(f"Created new thread in memory with ID: {thread_id}")
    else:
        logger.info(f"Using existing thread with ID: {thread_id}")
        if thread_id not in in_memory_threads:
            logger.info(f"Thread with ID {thread_id} not found in memory. Creating it.")
            in_memory_threads[thread_id] = []

    # Fetch existing messages in this thread
    messages = in_memory_threads.get(thread_id, [])

    # Get the agent and initializer from functions_for_pipeline
    agent_app, initialize_agent_state = create_agent()

    # Initialize agent state with the query and a hardcoded default persona
    default_persona = "standard"
    logger.info(f"Using default persona: {default_persona}")
    state = initialize_agent_state(clean_prompt, persona=default_persona)

    # Execute the agent
    logger.info("Executing pharma specialized agent")
    result = agent_app.invoke(state)

    # Extract the response from the result
    response_content = result.get("response", "No response generated")
    logger.info(f"Pharma agent response: {response_content}")

    # Create AI message with the response
    ai_message = {
        "message_id": str(uuid.uuid4()),
        "message_type": "ai",
        "message_content": response_content,
        "message_extra": {},
        "created_at": datetime.now().isoformat()
    }

    # Create human message for the current prompt
    human_message = {
        "message_id": str(uuid.uuid4()),
        "message_type": "human",
        "message_content": prompt,
        "message_extra": {},
        "created_at": datetime.now().isoformat()
    }

    # Add messages to thread history
    new_messages = [human_message, ai_message]
    current_thread_history = in_memory_threads.get(thread_id, [])
    current_thread_history.extend(new_messages)
    in_memory_threads[thread_id] = current_thread_history

    # Determine which messages to return
    messages_to_return = new_messages if return_new_messages_only else current_thread_history

    # Prepare response
    response = {
        "thread_id": thread_id,
        "messages": _convert_message_format(messages_to_return),
        "source_documents": []  # No source documents for pharma agent
    }

    logger.info(f"Pharma agent handler completed - returning {len(response['messages'])} messages")
    logger.info("="*50)

    return response
