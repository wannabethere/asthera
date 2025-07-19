import json
import re
import logging
import asyncio
import time
from typing import Dict, List, Any, Literal, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
import pprint
from app.utils.llm_factory import get_splitter_llm, get_default_llm

load_dotenv()

# Set up logging
logger = logging.getLogger("QuerySplitter")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== QuerySplitter logger initialized ===")

# Topic keywords for different domains
TOPIC_KEYWORDS = {
    'technology': ['software', 'computer', 'algorithm', 'programming', 'data', 'api', 'database'],
    'business': ['revenue', 'profit', 'customer', 'market', 'sales', 'strategy', 'company'],
    'science': ['research', 'study', 'analysis', 'experiment', 'hypothesis', 'conclusion'],
    'health': ['medical', 'patient', 'treatment', 'diagnosis', 'healthcare', 'medicine'],
    'education': ['student', 'teacher', 'learning', 'course', 'university', 'academic']
}

# Sales conversation categories - commented out as we're focusing on CSOD
"""
SALES_CATEGORIES = [
    "Customer Pain Point",
    "Product Feature Discussed", 
    "Objection Raised",
    "Next Step / CTA",
    "Competitor Mentioned",
    "Decision Criteria",
    "Buyer Role / Persona",
    "Sales Rep Talk Ratio",
    "Deal Stage or Intent",
    "Use Case Mentioned"
]
"""

# CSOD categories
CSOD_CATEGORIES = [
    "Learning Activity",
    "Training Completion",
    "Course Assignment",
    "User Organization",
    "Certification Status",
    "Learning Object",
    "Transcript Record",
    "Organizational Unit",
    "Learning Progress",
    "User Profile"
]

class SplitQueryResult(BaseModel):
    """Result of splitting a query into source-specific questions with topic classification."""
    # Comment out Gong and Salesforce fields
    """
    gong_question: str = Field(description="Question optimized for Gong transcript data")
    gong_topics: List[str] = Field(description="Relevant sales conversation topics for Gong data")
    salesforce_question: str = Field(description="Question optimized for Salesforce CRM data")
    salesforce_topics: List[str] = Field(description="Relevant sales topics for Salesforce data")
    """
    # Add CSOD fields
    csod_question: str = Field(description="Question optimized for CSOD learning management data")
    csod_topics: List[str] = Field(description="Relevant learning management topics for CSOD data")
    original_question: str = Field(description="The original user question")
    confidence: float = Field(description="Confidence score for the split (0.0-1.0)")
    # Modify priority to only include CSOD
    # priority: Literal["gong", "salesforce", "parallel"] = Field(description="Priority level for processing the query options: 'gong', 'salesforce', 'parallel'")
    priority: Literal["csod"] = Field(description="Priority level for processing the query, always 'csod'")

class QueryReformulationResult(BaseModel):
    """Result of reformulating a query for better relevance."""
    reformulated_query: str = Field(description="The reformulated query")
    reasoning: str = Field(description="Explanation of why the query was reformulated")
    target_keywords: List[str] = Field(description="Key terms that should improve relevance")

class FollowUpResult(BaseModel):
    """Result of follow-up question analysis and rephrasing."""
    is_follow_up: bool = Field(description="Whether this is a follow-up question requiring context")
    standalone_question: str = Field(description="The rephrased standalone question")
    reasoning: str = Field(description="Explanation of why it was rephrased")
    confidence: float = Field(description="Confidence score for the follow-up detection (0.0-1.0)")

# Initialize LLMs with structured output
logger.info("Initializing LLM models for query splitting")
llm_split = get_splitter_llm(seed=42).with_structured_output(SplitQueryResult)
logger.info(f"Using model for query splitting (RunnableSequence instance)")
llm_followup = get_default_llm(task_name="followup_detection", seed=42).with_structured_output(FollowUpResult)
llm_reformulate = get_default_llm(task_name="query_reformulation", seed=42).with_structured_output(QueryReformulationResult)

def _format_chat_history_for_context(messages: List[Dict[str, Any]]) -> List[Any]:
    """
    Convert message history from internal format to LangChain format.
    
    Args:
        messages: List of messages in internal format with message_type and message_content
        
    Returns:
        List of LangChain Message objects
    """
    formatted_messages = []
    for msg in messages:
        message_type = msg.get("message_type", "")
        content = msg.get("message_content", "")

        # Ensure content is a string. If it's a dict or list from jsonb, convert it to a string.
        if isinstance(content, (dict, list)):
            content = json.dumps(content)
        elif not isinstance(content, str):
            content = str(content)
        
        if message_type == "human":
            formatted_messages.append(HumanMessage(content=content))
        elif message_type == "ai":
            formatted_messages.append(AIMessage(content=content))
    
    return formatted_messages

async def detect_and_rephrase_followup(
    user_question: str,
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> FollowUpResult:
    """
    Detect if a question is a follow-up and rephrase it to be standalone using chat history.
    
    Args:
        user_question: The current user question
        chat_history: Previous conversation messages in internal format
        
    Returns:
        FollowUpResult with standalone question if it was a follow-up
    """
    logger.info(f"[detect_and_rephrase_followup] Analyzing question: '{user_question}'")
    
    # If no chat history, it can't be a follow-up
    if not chat_history or len(chat_history) == 0:
        logger.info("[detect_and_rephrase_followup] No chat history - not a follow-up")
        return FollowUpResult(
            is_follow_up=False,
            standalone_question=user_question,
            reasoning="No previous conversation context available",
            confidence=1.0
        )
    
    # Create the contextualize prompt based on LangChain 2025 patterns
    contextualize_prompt = ChatPromptTemplate.from_messages([
        (
            "system", 
            "Given a chat history and the latest user question which might reference "
            "context in the chat history, determine if this is a follow-up question. "
            "If it is, formulate a standalone question that can be understood without the chat history. "
            "Do NOT answer the question, just reformulate it if needed.\n\n"
            
            "**IMPORTANT**: When reformulating, you MUST preserve all key entities, names, and constraints "
            "from the previous context (like timeframes, people's names, specific topics) unless the new question "
            "explicitly overrides them. The goal is to add context, not to lose it.\n\n"
            
            "Example:\n"
            "Chat History:\n"
            "Human: 'Which courses have the highest completion rates in the last 1 month?'\n"
            "AI: (lists some courses)\n"
            "Latest User Question:\n"
            "Human: 'Which of these were mandatory trainings?'\n"
            "Correct Standalone Question:\n"
            "'Of the courses with the highest completion rates in the last month, which of them were mandatory trainings?'\n\n"

            "Follow-up indicators include:\n"
            "- Pronouns like 'it', 'that', 'they', 'this', 'these'\n"
            "- Implicit references like 'more details', 'what else', 'anything else'\n"
            "- Continuation words like 'also', 'additionally', 'furthermore'\n\n"

            "If it's NOT a follow-up question (it's a complete and standalone new question), return the "
            "original question unchanged."
        ),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    
    try:
        # Format chat history for LangChain
        formatted_history = _format_chat_history_for_context(chat_history)
        logger.info(f"[detect_and_rephrase_followup] Formatted {len(formatted_history)} messages for context")
        
        # Create the chain by piping the prompt template to the LLM
        chain = contextualize_prompt | llm_followup

        # Invoke the chain to analyze the question
        response = await chain.ainvoke({
            "chat_history": formatted_history,
            "input": user_question
        })
        
        logger.info(f"[detect_and_rephrase_followup] Follow-up detection result: is_follow_up={response.is_follow_up}")
        if response.is_follow_up:
            logger.info(f"[detect_and_rephrase_followup] Standalone question: '{response.standalone_question}'")
            logger.info(f"[detect_and_rephrase_followup] Reasoning: {response.reasoning}")
        
        return response

    except Exception as e:
        logger.error(f"[detect_and_rephrase_followup] Error analyzing follow-up question: {e}")
        
        # Fallback: return as not a follow-up
        logger.warning("[detect_and_rephrase_followup] Falling back to original question")
        return FollowUpResult(
            is_follow_up=False,
            standalone_question=user_question,
            reasoning=f"Error during analysis: {str(e)}",
            confidence=0.0
        )

async def split_user_question(
    user_question: str,
    context: Optional[Dict[str, Any]] = None
) -> SplitQueryResult:
    """
    Split a user question into specialized questions for different data sources with topic classification.
    Now focusing only on CSOD data.
    
    Args:
        user_question: The original user question
        context: Optional context about previous interactions or document types
        
    Returns:
        SplitQueryResult with questions tailored for the CSOD data source and relevant topics
    """
    logger.info(f"[split_user_question] Optimizing question for CSOD: '{user_question}'")
    
    system_prompt = f"""You are an expert at analyzing user questions and optimizing them for the CSOD (Cornerstone OnDemand) learning management system data source with topic classification.
    
    Your task is to take a user question and create an optimized version for the CSOD data source, 
    along with identifying relevant learning management topics.
    
    AVAILABLE TOPIC KEYWORDS: {TOPIC_KEYWORDS}
    
    CSOD LEARNING MANAGEMENT CATEGORIES: {CSOD_CATEGORIES}

    **IMPORTANT: FOR TOPIC EXTRACTION, DO NOT USE GENERIC CATEGORIES DIRECTLY. INSTEAD, EXTRACT SPECIFIC TERMS FROM THE USER'S QUERY.**
    
    For example:
    - For a query "Which users completed the compliance training in the last month?", extract terms like ["users", "compliance training", "completed", "month"]
    - For a query about "Which courses have the highest assignment rates?", extract terms like ["courses", "assignment rates", "highest"]
    - PREFER SPECIFIC TERMS FROM THE QUERY OVER GENERIC CATEGORIES
    
    DATA SOURCE:
    
    CSOD (Cornerstone OnDemand Learning Management System):
       - Main data: User organizational information, learning activities, transcripts, course completions
       - Each document contains: document_id, source data fields, and metadata
       - Example data fields include: user_ou_info_user_id, reg_num, lo_object_id
       - Metadata includes: extractedEntities, sourceFile, sourceType, recordIndex
       - The data is specifically from a learning management system and contains information about users,
         training courses, completions, organizational units, and learning activities.
    
    QUESTION OPTIMIZATION GUIDELINES:
    
    For CSOD questions:
    - Focus on learning management aspects: users, courses, training, organizational units, learning activities
    - Include terms like "learning", "training", "course", "user", "transcript" ONLY IF they are not already implied
    - DO NOT add unnecessary terms if the query is already specific
    - EXTRACT SPECIFIC TERMS FROM THE QUERY (names, activities, timeframes, etc.)
    - PRESERVE the original query intent - do not over-embellish
    
    TOPIC IDENTIFICATION:
    - EXTRACT SPECIFIC TERMS AND ENTITIES FROM THE USER'S QUESTION (e.g., "compliance training", "users", "completed")
    - For csod_topics: Extract specific entities, actions, timeframes and other key terms from the query
    - DO NOT just use generic categories unless they directly appear in the query
    
    EXAMPLES:
    
    Example 1:
    Original: "Show me which users haven't completed compliance training yet"
    Output:
    {{
        "csod_question": "Which users in the CSOD system haven't completed their assigned compliance training courses yet?",
        "csod_topics": ["users", "compliance training", "completed", "assigned"],
        "original_question": "Show me which users haven't completed compliance training yet",
        "confidence": 0.9,
        "priority": "csod"
    }}
    
    Example 2:
    Original: "What are the most popular courses this quarter?"
    Output:
    {{
        "csod_question": "Which learning objects or courses in CSOD have the highest enrollment or completion rates this quarter?",
        "csod_topics": ["courses", "popular", "quarter", "enrollment", "completion rates"],
        "original_question": "What are the most popular courses this quarter?",
        "confidence": 0.9,
        "priority": "csod"
    }}
    
    Example 3:
    Original: "Which organizational units have the lowest training completion rates?"
    Output:
    {{
        "csod_question": "Which organizational units in the CSOD system have the lowest percentage of completed training activities or courses?",
        "csod_topics": ["organizational units", "training", "completion rates", "lowest"],
        "original_question": "Which organizational units have the lowest training completion rates?",
        "confidence": 0.85,
        "priority": "csod"
    }}
    
    Output your response as a JSON object with this exact structure:
    {{
        "csod_question": "question optimized for CSOD learning management data",
        "csod_topics": ["specific", "query", "terms"],
        "original_question": "the original user question",
        "confidence": 0.85,
        "priority": "csod"
    }}
    """
    
    context_info = ""
    if context:
        context_info = f"\n\nAdditional context: {context}"
    
    try:
        response = await llm_split.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Original question: {user_question}{context_info}\n\nPlease optimize this question for the CSOD data source and identify relevant topics.")
        ])
        
        logger.info(f"[split_user_question] LLM response received")
        return response

    except Exception as e:
        logger.error(f"[split_user_question] Error optimizing question: {e}")
    
        # Fallback: return the original question
        logger.warning("[split_user_question] Falling back to original question")
        return SplitQueryResult(
            csod_question=user_question,
            csod_topics=[],
            original_question=user_question,
            confidence=0.0,
            priority="csod"
        )

async def reformulate_query_for_relevance(
    original_query: str,
    retrieved_documents: List[Dict[str, Any]],
    user_question: str,
    data_source: str = "csod"  # Changed default to csod
) -> QueryReformulationResult:
    """
    Reformulate a query when retrieved documents are not relevant enough.
    
    Args:
        original_query: The query that didn't return relevant results
        retrieved_documents: List of documents that were retrieved (with low relevance)
        user_question: The original user question for context
        data_source: The type of data source being queried (default is now "csod")
        
    Returns:
        QueryReformulationResult with improved query and reasoning
    """
    logger.info(f"[reformulate_query_for_relevance] Reformulating query for {data_source}: '{original_query}'")
    
    # Analyze the retrieved documents to understand what was found
    doc_analysis = []
    if retrieved_documents:
        for i, doc in enumerate(retrieved_documents[:5]):  # Analyze top 5 docs
            doc_analysis.append({
                "id": doc.get("document_id", f"doc_{i}"),
                "type": doc.get("document_type", "unknown"),
                "relevance_score": doc.get("relevance_score", 0.0),
                "metadata_keys": list(doc.get("metadata", {}).keys()) if doc.get("metadata") else []
            })
    
    system_prompt = f"""You are an expert at query reformulation for document retrieval systems.
    
    The current query did not retrieve sufficiently relevant documents from the {data_source} data source.
    Your task is to reformulate the query to improve relevance and retrieval quality.
    
    DATA SOURCE SPECIFIC GUIDANCE:
    
    For CSOD (learning management data):
    - Use learning management terms: "course", "training", "learning object", "transcript", "user"
    - Include educational context: "completion", "assignment", "enrollment", "certification"
    - Focus on organizational structure: "organizational unit", "user group", "division"
    
    # Comment out guidance for other sources since we're focusing on CSOD
    """
    """
    For GONG (call transcripts):
    - Use conversational terms: "discussed", "mentioned", "talked about", "call", "meeting"
    - Include emotional context: "concerns", "objections", "excitement", "questions"
    - Focus on interaction: "customer said", "we explained", "they asked"
    
    For SALESFORCE (CRM data):
    - Use CRM terminology: "opportunity", "deal", "account", "pipeline", "forecast"
    - Include sales stages: "closed won", "proposal", "negotiation", "qualified"
    - Focus on metrics: "revenue", "close date", "probability", "amount"
    
    For PDF (documents):
    - Use formal terms: "document", "report", "policy", "procedure", "analysis"
    - Include document types: "presentation", "manual", "guide", "specification"
    - Focus on content: "contains", "describes", "outlines", "details"
    
    REFORMULATION STRATEGIES:
    1. Add synonyms and related terms
    2. Use more specific terminology for the data source
    3. Include contextual keywords that appear in relevant documents
    4. Simplify overly complex queries or make simple queries more specific
    5. Use domain-specific language that matches the data source
    
    Output your response as a JSON object:
    {{
        "reformulated_query": "the improved query text",
        "reasoning": "explanation of changes made and why",
        "target_keywords": ["keyword1", "keyword2", "keyword3"],
        "confidence": 0.85
    }}
    """
    
    context = {
        "original_query": original_query,
        "user_question": user_question,
        "data_source": data_source,
        "retrieved_docs_analysis": doc_analysis,
        "num_docs_retrieved": len(retrieved_documents)
    }
    
    try:
        # Add delay to avoid rate limiting
        await asyncio.sleep(0.3)
        
        response = await llm_reformulate.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Context:\n{json.dumps(context, indent=2)}\n\nPlease reformulate the query for better relevance.")
        ])
        
        logger.info(f"[reformulate_query_for_relevance] LLM response received")
        logger.info(f"[reformulate_query_for_relevance] Successfully reformulated query")
        logger.info(f"[reformulate_query_for_relevance] New query: {response.reformulated_query}")
        logger.info(f"[reformulate_query_for_relevance] Target keywords: {response.target_keywords}")
        
        return response
                
    except Exception as e:
        logger.error(f"[reformulate_query_for_relevance] Error reformulating query: {e}")
    
    # Fallback: simple reformulation
    logger.warning("[reformulate_query_for_relevance] Falling back to simple reformulation")
    
    # Simple keyword enhancement based on data source (focusing on CSOD)
    enhanced_query = original_query
    if data_source == "csod":
        enhanced_query = f"learning training course user transcript {original_query}"
    # Comment out other data sources
    """
    elif data_source == "gong":
        enhanced_query = f"call transcript meeting discussed {original_query}"
    elif data_source == "salesforce":
        enhanced_query = f"opportunity deal account sales {original_query}"
    elif data_source == "pdf":
        enhanced_query = f"document report analysis {original_query}"
    """
    
    return QueryReformulationResult(
        reformulated_query=enhanced_query,
        reasoning="Applied simple keyword enhancement due to reformulation error",
        target_keywords=enhanced_query.split()[:5]
    )

# Enhanced function that combines follow-up detection and query splitting
async def smart_query_processor(
    user_question: str,
    relevance_threshold: float = 0.5,
    context: Optional[Dict[str, Any]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Comprehensive query processing that handles follow-up questions, splits questions and reformulates if needed.
    Modified to focus on CSOD data source.
    
    Args:
        user_question: The original user question
        relevance_threshold: Minimum relevance score to consider documents relevant
        context: Additional context for processing
        chat_history: Previous conversation messages for follow-up detection
        
    Returns:
        Dictionary containing follow-up analysis, CSOD-optimized query, topics, and reformulation if applicable
    """
    logger.info(f"[smart_query_processor] Processing question: '{user_question}'")
    
    start_time = time.time()
    
    # Dictionary to store all the results
    result = {
        "original_question": user_question,
        "topics": {},
        "processed_query": user_question,  # Default to original question
    }
    
    try:
        # Step 1: Detect if this is a follow-up question to previous conversation
        if chat_history:
            logger.info(f"[smart_query_processor] Analyzing if question is a follow-up with {len(chat_history)} messages of chat history")
            followup_result = await detect_and_rephrase_followup(user_question, chat_history)
            
            # Store follow-up analysis
            result["followup_analysis"] = {
                "is_follow_up": followup_result.is_follow_up,
                "standalone_question": followup_result.standalone_question,
                "reasoning": followup_result.reasoning,
                "confidence": followup_result.confidence
            }
            
            # If this is a follow-up, use the standalone version for further processing
            if followup_result.is_follow_up and followup_result.confidence > 0.7:
                logger.info(f"[smart_query_processor] Using standalone question for further processing: '{followup_result.standalone_question}'")
                processing_question = followup_result.standalone_question
            else:
                processing_question = user_question
        else:
            processing_question = user_question
            result["followup_analysis"] = {
                "is_follow_up": False,
                "standalone_question": user_question,
                "reasoning": "No chat history provided",
                "confidence": 1.0
            }
        
        # Step 2: Split the question for CSOD data
        logger.info(f"[smart_query_processor] Splitting question for CSOD data: '{processing_question}'")
        split_result = await split_user_question(processing_question, context)
        
        # Store CSOD-specific query and topics
        result["csod_query"] = split_result.csod_question
        result["topics"]["csod_topics"] = split_result.csod_topics
        result["priority"] = "csod"  # Always use CSOD priority
        
        # Store combined topics for convenience
        result["topics"]["topics"] = split_result.csod_topics
        
        # Set default processed query to the CSOD query
        result["processed_query"] = split_result.csod_question
        
        logger.info(f"[smart_query_processor] Generated CSOD query: '{split_result.csod_question}'")
        logger.info(f"[smart_query_processor] Identified {len(split_result.csod_topics)} CSOD topics: {split_result.csod_topics}")
        
        # Finished processing
        processing_time = time.time() - start_time
        logger.info(f"[smart_query_processor] Processing completed in {processing_time:.2f} seconds")
        
        return result
    
    except Exception as e:
        logger.error(f"[smart_query_processor] Error processing query: {e}")
        import traceback
        logger.error(f"[smart_query_processor] Traceback: {traceback.format_exc()}")
        
        # Return simple fallback result
        result["processed_query"] = user_question
        result["priority"] = "csod"
        
        # Try to extract some basic topics
        basic_topics = [word for word in user_question.lower().split() if len(word) > 3]
        result["topics"]["csod_topics"] = basic_topics
        result["topics"]["topics"] = basic_topics
        
        return result

# if __name__ == "__main__":
#     result = asyncio.run(smart_query_processor("Show accounts with stagnant pipeline (no activity in 60+ days)."))
#     pprint.pprint(result)