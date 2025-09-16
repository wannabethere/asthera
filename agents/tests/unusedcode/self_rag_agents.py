import logging
import time
import datetime
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Annotated, Sequence, Union
import asyncio
import uuid
from datetime import datetime, timedelta

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import operator
from enum import Enum

from chromadb import Collection

from app.schemas.document_schemas import DocumentType
from app.utils.chromadb import ChromaDB
from app.config.settings import get_settings
from app.utils.postgresdb import PostgresDB
from app.utils.time_checkpoint import checkpoint
from app.models.sfdc_models import (
    SFDC_TABLE_SCHEMAS,
    ACCOUNT_TABLE_SCHEMA_PROMPT,
    OPPORTUNITY_TABLE_SCHEMA_PROMPT,
    # Commented out imports for tables we're not using
    # CONTACT_TABLE_SCHEMA_PROMPT,
    # LEAD_TABLE_SCHEMA_PROMPT,
    # TASK_TABLE_SCHEMA_PROMPT,
    # USER_TABLE_SCHEMA_PROMPT
)

if TYPE_CHECKING:
    from langgraph.graph.graph import CompiledGraph

# Enhanced logger setup with more detailed format
logger = logging.getLogger("SelfRAGDocumentChat")
logger.setLevel(logging.DEBUG)
# Create console handler if not already added
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== Self-RAG Logger Initialized ===")

# Define state types
class QueryType(str, Enum):
    INITIAL = "initial"
    REFINED = "refined"

class DocumentSource(BaseModel):
    document_id: str
    document_type: str
    relevance_score: float = Field(default=0.0)
    
class RetrievedDocument(BaseModel):
    document_id: str
    document_type: str
    content: dict
    relevance_score: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    insights: List[Dict[str, Any]] = Field(default_factory=list)

class SelfRAGState(BaseModel):
    """State for the Self-RAG document chat agent."""
    question: str
    source: str
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    current_query: str = ""
    query_type: QueryType = QueryType.INITIAL
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    selected_documents: List[RetrievedDocument] = Field(default_factory=list)
    sfdc_query_results: List[Dict[str, Any]] = Field(default_factory=list)
    sfdc_tables: List[str] = Field(default_factory=list)
    context: str = ""
    reflection: str = ""
    needs_more_info: bool = False
    answer: str = ""
    final_answer: str = ""
    document_ids: List[str] = Field(default_factory=list)  # List of specific document IDs to use
    recursion_count: int = Field(default=0)  # Counter for number of query refinements

def get_doc_store(doc_type: DocumentType) -> Collection:
    """Get the document store for the given document type."""
    chroma_db = ChromaDB()
    return chroma_db.get_collection(doc_type.value)

def get_documents_query(query: str, n_results: int = 25) -> List[Dict[str, Any]]:
    """
    Query the document store for documents matching the query.
    
    Args:
        query: The search query text
        n_results: Maximum number of results to return
        
    Returns:
        List of document dictionaries with relevance scores
    """
    
    logger.info(f"Querying documents with query: '{query}'")
    chroma_db = ChromaDB()
    all_documents = []
    
    # Only use the "documents" collection
    collection_name = "documents"
    
    try:
        logger.info(f"Querying collection '{collection_name}' with time-based filtering")
        
        # Use proper timestamp-based filtering now that we have date_timestamp field
        try:
            now = datetime.now()
            timestamp_120_days_ago = (now - timedelta(days=120)).timestamp()
            logger.info(f"Filtering documents newer than {timestamp_120_days_ago} ({datetime.fromtimestamp(timestamp_120_days_ago)})")
            
            # Apply the date_timestamp filter to get recent documents
            results = chroma_db.query_collection_with_relevance_scores(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results,
                where={"date_timestamp": {"$gt": timestamp_120_days_ago}}
            )
            
            # If no results with timestamp filter, fall back to unfiltered search
            if not results or len(results) == 0:
                logger.warning("No results found with date_timestamp filter, falling back to unfiltered search")
                results = chroma_db.query_collection_with_relevance_scores(
                    collection_name=collection_name,
                    query_texts=[query],
                    n_results=n_results
                )
                
        except Exception as filter_err:
            logger.error(f"Error with date-filtered query: {filter_err}, falling back to unfiltered query")
            results = chroma_db.query_collection_with_relevance_scores(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results
            )
        
        logger.info(f"Found {len(results)} results in collection '{collection_name}'")
        
        # Add collection name to each document for tracking
        for doc in results:
            doc['collection'] = collection_name
            all_documents.append(doc)
            
        # Log relevance score statistics
        if all_documents:
            rel_scores = [doc.get('relevance_score', 0) for doc in all_documents]
            logger.info(f"Relevance scores - min: {min(rel_scores):.4f}, max: {max(rel_scores):.4f}, avg: {sum(rel_scores)/len(rel_scores):.4f}")
            logger.info(f"Top 5 relevance scores: {rel_scores[:5]}")
            
    except Exception as e:
        logger.warning(f"Error querying collection {collection_name}: {e}")
    
    logger.info(f"Total documents found: {len(all_documents)}")
    
    # Sort all documents by relevance score
    sorted_documents = sorted(all_documents, key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    # Take the top n_results
    return sorted_documents[:n_results]
    

def get_sfdc_tables() -> str:
    """Get the list of Salesforce tables."""
    return "\n\n".join([ACCOUNT_TABLE_SCHEMA_PROMPT,
            OPPORTUNITY_TABLE_SCHEMA_PROMPT])
    # Original implementation commented out:
    # return "\n\n".join([ACCOUNT_TABLE_SCHEMA_PROMPT,
    #        CONTACT_TABLE_SCHEMA_PROMPT,
    #        LEAD_TABLE_SCHEMA_PROMPT,
    #        OPPORTUNITY_TABLE_SCHEMA_PROMPT,
    #        TASK_TABLE_SCHEMA_PROMPT,
    #        USER_TABLE_SCHEMA_PROMPT])

def get_sfdc_tables_prompt_bykey(key: List[str]) -> str:
    """Get the list of Salesforce tables."""
    tables = []
    
    # Debug the incoming keys
    logger.info(f"Getting SFDC table schemas for keys: {key}")
    
    # Define allowed tables
    allowed_tables = ["salesforce_opportunities", "salesforce_accounts"]
    
    if not key or not isinstance(key, list):
        logger.warning(f"Invalid SFDC table keys: {key}. Using default table Opportunity.")
        # Default to Opportunity if no valid keys
        return SFDC_TABLE_SCHEMAS["salesforce_opportunities"]
    
    for table in key:
        # Clean up any quotes or spaces in the table name
        if isinstance(table, str):
            # Strip quotes and spaces
            clean_table = table.strip().strip('"\'').strip()
            logger.info(f"Processing SFDC table: {table} (cleaned to: {clean_table})")
            
            # Check if the cleaned table name is in our allowed tables
            if clean_table in allowed_tables and clean_table in SFDC_TABLE_SCHEMAS:
                tables.append(SFDC_TABLE_SCHEMAS[clean_table])
            else:
                # Try to find a case-insensitive match among allowed tables
                found = False
                for schema_key in SFDC_TABLE_SCHEMAS.keys():
                    if schema_key.lower() == clean_table.lower() and schema_key in allowed_tables:
                        logger.info(f"Found case-insensitive match for {clean_table}: {schema_key}")
                        tables.append(SFDC_TABLE_SCHEMAS[schema_key])
                        found = True
                        break
                
                if not found:
                    logger.warning(f"Table {clean_table} not found in allowed tables or SFDC_TABLE_SCHEMAS, skipping")
        else:
            logger.warning(f"Skipping non-string table key: {table}")
    
    # If no valid tables were found, default to Opportunity
    if not tables:
        logger.warning("No valid tables found, defaulting to Opportunity")
        tables.append(SFDC_TABLE_SCHEMAS["salesforce_opportunities"])
    
    return "\n\n".join(tables)

class SelfRAGDocumentChat:
    """
    A class that implements a document chat agent using Self-RAG architecture.
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the SelfRAGDocumentChat agent."""
        self.agent = None
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0)
        self.source_types_supported = [
            DocumentType.GONG_TRANSCRIPT,
            DocumentType.GENERIC
        ]
        self.sfdc_tables = get_sfdc_tables()
        
    def _init_graph(self) -> "CompiledGraph":
        start_time = time.time()
        checkpoint_time = checkpoint("Initializing SelfRAGDocumentChat agent", start_time)
        
        # Get API key from settings
        settings = get_settings()
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")

        # Store the latest state for error recovery
        self.latest_state = None
       
        checkpoint_time = checkpoint("Initialized ChatOpenAI model", checkpoint_time)
        
        # 2. Create the state graph for the Self-RAG workflow
        workflow = StateGraph(SelfRAGState)
        
        # Define the nodes (these are the key steps in the Self-RAG process)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("analyze_retrieval", self._analyze_retrieval)
        workflow.add_node("query_formation", self._query_formation)
        workflow.add_node("retrieve_full_documents", self._retrieve_full_documents)
        workflow.add_node("get_sfdc_table_schema", self._get_sfdc_table_schema)
        workflow.add_node("query_sfdc", self._query_sfdc)
        workflow.add_node("generate_answer", self._generate_answer)
        workflow.add_node("reflect", self._reflect)
        workflow.add_node("finalize", self._finalize)
        workflow.add_node("check_recursion", self._check_recursion_limit)
        
        # 3. Define the edges (this is the flow of the Self-RAG process)
        # Start with retrieval
        workflow.set_entry_point("retrieve")
        
        # After retrieval, analyze what was retrieved
        workflow.add_edge("retrieve", "analyze_retrieval")
        
        # After analysis, check recursion count first
        workflow.add_edge("analyze_retrieval", "check_recursion")
        
        # Based on recursion check, decide whether to continue or end
        workflow.add_conditional_edges(
            "check_recursion",
            self._is_recursion_limit_reached,
            {
                True: "finalize",  # If recursion limit reached, go straight to finalize
                False: "analyze_retrieval_decision"  # Otherwise proceed with normal flow
            }
        )
        
        # Add a decision point after analyze_retrieval
        workflow.add_node("analyze_retrieval_decision", lambda x: x)
        
        # Based on analysis, decide whether to refine the query or proceed
        workflow.add_conditional_edges(
            "analyze_retrieval_decision",
            self._should_refine_query,
            {
                True: "query_formation",  # If we need better results, refine the query
                False: "retrieve_full_documents"  # If results are good, retrieve full documents
            }
        )
        
        # If we refined the query, go back to retrieval
        workflow.add_edge("query_formation", "retrieve")
        
        # After retrieving full documents, check if we need SFDC data
        workflow.add_conditional_edges(
            "retrieve_full_documents",
            self._needs_sfdc_data,
            {
                True: "get_sfdc_table_schema",  # If we need SFDC data, query it
                False: "generate_answer"  # Otherwise, generate the answer
            }
        )
        
        # After querying SFDC, generate an answer
        workflow.add_edge("get_sfdc_table_schema", "query_sfdc")
        workflow.add_edge("query_sfdc", "generate_answer")
        
        # After generating the answer, reflect on it
        workflow.add_edge("generate_answer", "reflect")
        
        # Based on reflection, decide whether to finalize or go back for more information
        workflow.add_conditional_edges(
            "reflect",
            self._is_answer_sufficient,
            {
                True: "finalize",  # If the answer is sufficient, finalize it
                False: "query_formation"  # If we need more info, refine the query
            }
        )
        
        # Finalize is the end of the process
        workflow.add_edge("finalize", END)
        
        # Compile the graph with recursion limit
        self.agent = workflow.compile()
        checkpoint_time = checkpoint("Compiled Self-RAG workflow graph", checkpoint_time)
        
        return self.agent
        
    async def _check_recursion_limit(self, state: SelfRAGState) -> SelfRAGState:
        """Check if recursion limit is reached and handle it."""
        # Increment recursion counter on each pass through this node
        state.recursion_count += 1
        logger.info(f"[_check_recursion_limit] Recursion count: {state.recursion_count}")
        
        return state
        
    def _is_recursion_limit_reached(self, state: SelfRAGState) -> bool:
        """Determine if we've reached recursion limit."""
        # Check if we've hit our defined limit (2)
        if state.recursion_count >= 2:
            logger.info("[_is_recursion_limit_reached] Recursion limit reached, moving to finalize")
            
            # Set final_answer based on best available information
            if state.answer:
                state.final_answer = state.answer
                logger.info("[_is_recursion_limit_reached] Using existing answer for final output")
            elif state.selected_documents:
                state.final_answer = f"Based on the available documents, here's what I found:\n\n"
                for i, doc in enumerate(state.selected_documents[:5]):
                    if hasattr(doc, 'content'):
                        content = doc.content
                        if isinstance(content, dict):
                            if 'text' in content:
                                content = content['text']
                            else:
                                for field in ['content', 'transcript', 'body', 'data']:
                                    if field in content:
                                        content = content[field]
                                        break
                                else:
                                    content = str(content)
                        content = str(content)[:300].strip()
                        state.final_answer += f"**Document {i+1}**: {content}...\n\n"
                logger.info("[_is_recursion_limit_reached] Generated summary from documents for final output")
            elif state.retrieved_documents:
                state.final_answer = f"Based on the retrieved documents, here's what I found:\n\n"
                for i, doc in enumerate(state.retrieved_documents[:5]):
                    if isinstance(doc, dict):
                        doc_id = doc.get('document_id', f"Document {i+1}")
                        doc_type = doc.get('document_type', 'unknown')
                        state.final_answer += f"**Document {i+1}** (ID: {doc_id}, Type: {doc_type})\n\n"
                logger.info("[_is_recursion_limit_reached] Generated document list for final output")
            else:
                state.final_answer = f"I analyzed your question but couldn't find specific information about '{state.question}'. Please try rephrasing your question or providing more details."
                logger.info("[_is_recursion_limit_reached] No useful content available, using default response")
            
            return True
        return False
        
    def _should_refine_query(self, state: SelfRAGState) -> bool:
        """Determine if we should refine the query based on the analysis."""
        logger.info("[_should_refine_query] Evaluating if query refinement is needed")
        
        # Skip refinement if specific document IDs are provided
        if state.document_ids:
            logger.info("[_should_refine_query] Specific document IDs provided, skipping refinement")
            return False
        
        # Check if we have enough relevant documents
        if len(state.retrieved_documents) < 2:
            logger.info("[_should_refine_query] Too few documents retrieved, refinement needed")
            return True
            
        # Check if the relevance scores are too low
        relevance_scores = [doc.get('relevance_score', 0) for doc in state.retrieved_documents[:25] if isinstance(doc, dict)]
        if relevance_scores and all(score < 0.5 for score in relevance_scores):
            logger.info(f"[_should_refine_query] Low relevance scores: {relevance_scores}, refinement needed")
            return True
            
        # If there's a clear indication in the reflection that we need to refine
        if "not relevant" in state.reflection.lower() or "reformulate" in state.reflection.lower():
            logger.info("[_should_refine_query] Reflection indicates need for refinement")
            return True
            
        logger.info("[_should_refine_query] Retrieval results are sufficient, no refinement needed")
        return False

    async def _query_formation(self, state: SelfRAGState) -> SelfRAGState:
        """Reformulate the query to be more effective."""
        logger.info(f"[_query_formation] Reformulating query, current recursion count: {state.recursion_count}")
        
        # Increment recursion counter
        state.recursion_count += 1
        logger.info(f"[_query_formation] Recursion count: {state.recursion_count}")
        
        # If we've hit the recursion limit, skip query formation
        if state.recursion_count >= 2:
            logger.info("[_query_formation] Maximum recursion count reached, skipping query formation")
            return state
        
        system_prompt = """You are an expert at query reformulation.
        The initial query did not retrieve relevant documents. 
        Your task is to reformulate the query to be more specific and targeted.
        Consider the user's original question and the previous query, and create a new query.
        Please use the following words in your query reformulation:
        ["opportunity", "deal", "sales", "pipeline", "forecast", 
                        "revenue", "salesforce", "account", "close date", "account","lead","activity","task","contact","associate","sales rep"]
        Your output should be the reformulated query as plain text."""
        
        context = {
            "original_question": state.question,
            "previous_query": state.current_query,
            "reflection": state.reflection
        }
        
        try:
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
            query_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Here is the context:\n{context}\n\nPlease reformulate the query.")
                ]
            )
            
            # Update state with the new query
            if isinstance(query_response.content, str):
                state.current_query = query_response.content.strip()
                state.query_type = QueryType.REFINED
            else:
                logger.warning("Query response content is not a string")
            
        except Exception as e:
            logger.error(f"Error reformulating query: {e}")
            # If there's an error, just keep the current query
            
        return state
    
    async def run_agent(
        self, 
        messages: List[Dict[str, Any]], 
        question: str, 
        source_type: Union[DocumentType, str],
        document_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run the agent with the given messages and prompt."""
        start_time = time.time()
        logger.info("="*50)
        logger.info(f"SELF-RAG AGENT STARTED - Question: '{question}'")
        logger.info(f"Source type: {source_type} (stored but not used for filtering)")
        logger.info(f"Time-based filtering: Documents from the last 120 days")
        logger.info(f"Chat history length: {len(messages)}")
        if document_ids:
            logger.info(f"Using specific document IDs: {document_ids}")
        logger.info("="*50)
        
        checkpoint_time = checkpoint("Invoking Self-RAG agent with messages", start_time)
        
        # Initialize the agent if it doesn't exist
        if self.agent is None:
            logger.info("Initializing Self-RAG agent graph")
            self.agent = self._init_graph()
            logger.info("Self-RAG agent graph initialized successfully")

        # Convert source_type to string if it's an enum
        source = source_type.value if isinstance(source_type, DocumentType) else source_type
        logger.info(f"Using source value in state: {source} (for backward compatibility only)")

        # Define a callback to track state updates during execution
        async def state_callback(state):
            self.latest_state = state
            logger.debug(f"State updated: {state}")
            return state

        # Prepare initial state
        state = SelfRAGState(
            question=question,
            chat_history=messages,
            current_query=question,
            source=source,
            document_ids=document_ids or []
        )
        # Store initial state
        self.latest_state = state
        logger.info(f"Initial state created with question: {question}")
        
        # Run the agent
        try:
            logger.info(f"Starting agent execution with question: {question}")
            
            # Create a wrapper for each node to capture state
            def wrap_node(node_func):
                async def wrapped_node(state):
                    try:
                        # Update latest state before processing
                        self.latest_state = state
                        result = await node_func(state)
                        # Update latest state after processing
                        self.latest_state = result
                        return result
                    except Exception as e:
                        # Log node error but keep the latest state
                        logger.error(f"Error in node {node_func.__name__}: {e}")
                        raise
                return wrapped_node
            
            # Wrap all nodes to capture state (if not already done)
            if not hasattr(self, "_nodes_wrapped"):
                for node_name in ["_retrieve", "_analyze_retrieval", "_query_formation", 
                                 "_retrieve_full_documents", "_get_sfdc_table_schema", 
                                 "_query_sfdc", "_generate_answer", "_reflect", "_finalize"]:
                    original = getattr(self, node_name)
                    setattr(self, node_name, wrap_node(original))
                self._nodes_wrapped = True
                
            result = await self.agent.ainvoke(state)
            logger.info(f"Agent execution completed, result type: {type(result)}")
            logger.info("="*50)
            logger.info("SELF-RAG AGENT EXECUTION COMPLETED")
            
            if hasattr(result, "keys"):
                logger.info(f"Result keys: {list(result.keys())}")
            checkpoint_time = checkpoint("Received Self-RAG agent response", checkpoint_time)
            
            # Format the response for the chat interface
            response = self._format_response(result)
            logger.info(f"Formatted response: {json.dumps(response)[:200]}...")
            checkpoint("Completed Self-RAG agent invocation", start_time)
            
            return response
        except Exception as e:
            logger.error(f"ERROR IN SELF-RAG AGENT: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Get the latest state we captured
            latest_state = self.latest_state
            logger.info(f"Latest state available: {latest_state is not None}")
            
            # If we have a state with an answer, use it
            if latest_state and latest_state.answer:
                return {
                    "messages": [
                        {
                            "message_type": "ai",
                            "message_content": latest_state.answer,
                            "message_id": f"ai_{int(time.time())}",
                            "message_extra": {}
                        }
                    ]
                }
            
            # If we have selected documents but no answer, generate a basic summary
            if latest_state and latest_state.selected_documents:
                message_content = "Based on the available documents, here's what I found:\n\n"
                for i, doc in enumerate(latest_state.selected_documents[:5]):
                    if hasattr(doc, 'content'):
                        content = doc.content
                        if isinstance(content, dict):
                            if 'text' in content:
                                content = content['text']
                            else:
                                for field in ['content', 'transcript', 'body', 'data']:
                                    if field in content:
                                        content = content[field]
                                        break
                                else:
                                    content = str(content)
                        content = str(content)[:300].strip()
                        message_content += f"**Document {i+1}**: {content}...\n\n"
                
                return {
                    "messages": [
                        {
                            "message_type": "ai",
                            "message_content": message_content,
                            "message_id": f"ai_{int(time.time())}",
                            "message_extra": {}
                        }
                    ]
                }
            
            # If we have nothing useful, return a simple error message
            return {
                "messages": [
                    {
                        "message_type": "ai",
                        "message_content": "I encountered an error while processing your request. Please try again.",
                        "message_id": f"ai_error_{int(time.time())}",
                        "message_extra": {}
                    }
                ]
            }
    
    def _format_response(self, result: Any) -> Dict[str, Any]:
        """Format the agent's response for the chat interface."""
        # Check if result is of expected type SelfRAGState
        if not isinstance(result, SelfRAGState):
            logger.error(f"Unexpected result type: {type(result)}")
            
            # If it's a LangGraph AddableValuesDict or dict, try to extract the state
            if hasattr(result, "get") and callable(result.get):
                # Try to access state fields from the dict-like object
                try:
                    # Extract fields we need for the response
                    final_answer = result.get("final_answer", "")
                    if not final_answer and "answer" in result:
                        final_answer = result.get("answer", "")
                    
                    selected_documents = result.get("selected_documents", [])
                    
                    # Create citations if available
                    cited_docs = []
                    for doc in selected_documents:
                        if hasattr(doc, "document_id") and hasattr(doc, "document_type"):
                            cited_docs.append({
                                "document_id": doc.document_id,
                                "document_type": doc.document_type
                            })
                        elif isinstance(doc, dict) and "document_id" in doc and "document_type" in doc:
                            cited_docs.append({
                                "document_id": doc["document_id"],
                                "document_type": doc["document_type"]
                            })
                    
                    # Format the response with any available answer
                    message_content = final_answer
                    if not message_content:
                        message_content = "I searched through the available documents but couldn't find specific information related to your query. Could you please provide more specific details or try a different question?"
                    
                    # Add citations if available
                    if cited_docs:
                        message_content += f"\n\n```json\n{{'documents': {cited_docs}}}\n```"
                    
                    # Return formatted response
                    return {
                        "messages": [
                            {
                                "message_type": "ai",
                                "message_content": message_content,
                                "message_id": f"ai_{int(time.time())}",
                                "message_extra": {}
                            }
                        ]
                    }
                except Exception as e:
                    logger.error(f"Error extracting state from result: {e}")
            
            # Return error response if extraction failed
            return {
                "messages": [
                    {
                        "message_type": "ai",
                        "message_content": "I encountered an error processing your request. Please try again.",
                        "message_id": f"ai_error_{int(time.time())}",
                        "message_extra": {}
                    }
                ]
            }
            
        # Create a list of used document citations
        cited_docs = []
        for doc in result.selected_documents:
            cited_docs.append({
                "document_id": doc.document_id,
                "document_type": doc.document_type
            })
        
        # Format the final answer with citations
        message_content = result.final_answer
        
        # Add the citations as JSON at the end if there are any
        if cited_docs:
            message_content += f"\n\n```json\n{{'documents': {cited_docs}}}\n```"
        
        # Create the response message
        response = {
            "messages": [
                {
                    "message_type": "ai",
                    "message_content": message_content,
                    "message_id": f"ai_{int(time.time())}",
                    "message_extra": {}
                }
            ]
        }
        
        return response
    
    # Node implementations
    # -------------------
    
    async def _retrieve(self, state: SelfRAGState) -> SelfRAGState:
        """Retrieve documents based on the current query."""
        query = state.current_query
        
        logger.info(f"[_retrieve] Starting document retrieval with query: '{query}'")
        
        # If specific document IDs are provided, use them directly
        if state.document_ids:
            logger.info(f"[_retrieve] Using specific document IDs: {state.document_ids}")
            retrieved_docs = []
            postgres_db = PostgresDB()
            chroma_db = ChromaDB()
            
            for doc_id in state.document_ids:
                try:
                    # Step 1: First try to find the document in PostgreSQL tables
                    found_in_postgres = False
                    for doc_type in ["generic", "gong_transcript"]:
                        table_name = f"document_{doc_type}"
                        record = postgres_db.get_record(table_name, doc_id)
                        if record:
                            # Found in PostgreSQL, now get additional metadata from ChromaDB
                            logger.info(f"[_retrieve] Found document {doc_id} in PostgreSQL table {table_name}")
                            
                            # Try to get metadata from ChromaDB
                            try:
                                # Only use the "documents" collection
                                all_metadata = {}
                                found_ids = []
                                
                                # Try different ID formats
                                possible_ids = [
                                    doc_id,               # Original ID
                                    f"doc_{doc_id}",      # doc_ prefix
                                ]
                                
                                # Add phrase_id pattern formats 
                                phrase_ids = [f"phrase_{doc_id}_{i}" for i in range(10)]  # Try suffixes _0 through _9
                                possible_ids.extend(phrase_ids)
                                
                                # Try each possible ID format in the documents collection
                                for pid in possible_ids:
                                    try:
                                        chroma_results = chroma_db.get_record("documents", pid)
                                        if chroma_results and chroma_results.get('ids') and len(chroma_results['ids']) > 0:
                                            found_ids.append(pid)
                                            logger.info(f"[_retrieve] Found metadata for ID format {pid} in ChromaDB documents collection")
                                            
                                            # Extract metadata
                                            if "metadatas" in chroma_results and chroma_results["metadatas"] and len(chroma_results["metadatas"]) > 0:
                                                doc_metadata = chroma_results["metadatas"][0]
                                                # Merge with existing metadata
                                                for key, value in doc_metadata.items():
                                                    if key not in all_metadata:
                                                        all_metadata[key] = value
                                    except Exception as ce:
                                        continue
                                    
                                # If we didn't find metadata by direct ID lookup, try metadata search
                                if not found_ids:
                                    try:
                                        results = chroma_db.query_collection_with_relevance_scores(
                                            collection_name="documents",
                                            query_texts=[""],  # Empty query to get all documents
                                            n_results=25,
                                            where={"document_id": {"$eq": doc_id}}  # Look for metadata with matching document_id
                                        )
                                        
                                        if results and len(results) > 0:
                                            logger.info(f"[_retrieve] Found metadata via search in ChromaDB documents collection")
                                            for result in results:
                                                if 'metadata' in result:
                                                    for key, value in result['metadata'].items():
                                                        if key not in all_metadata:
                                                            all_metadata[key] = value
                                    except Exception:
                                        continue
                                
                                logger.info(f"[_retrieve] Found {len(all_metadata)} metadata fields from ChromaDB")
                                
                            except Exception as e:
                                logger.warning(f"[_retrieve] Error getting metadata from ChromaDB: {e}")
                                all_metadata = {}
                            
                            # Create document object with both PostgreSQL content and ChromaDB metadata
                            doc = {
                                'document_id': doc_id,
                                'document_type': doc_type,
                                'content': record,
                                'collection': 'documents',  # Always use documents collection
                                'metadata': all_metadata,
                                'found_ids': found_ids if 'found_ids' in locals() else [],
                                'relevance_score': 1.0  # Assign maximum relevance as document was explicitly selected
                            }

                            # Try to get insights from the insights collection
                            try:
                                insights = []
                                # Query insights collection for this document
                                insight_results = chroma_db.query_collection_with_relevance_scores(
                                    collection_name="insights",
                                    query_texts=[""],  # Empty query to get all insights
                                    n_results=50,  # Increase to get all chunks' insights
                                    where={
                                        "$or": [
                                            {"parent_document_id": {"$eq": doc_id}},
                                            {"document_id": {"$eq": doc_id}}
                                        ]
                                    }
                                )
                                
                                if insight_results and len(insight_results) > 0:
                                    logger.info(f"[_retrieve] Found {len(insight_results)} insights for document {doc_id}")
                                    # Sort insights by chunk_index if available
                                    sorted_insights = sorted(
                                        insight_results,
                                        key=lambda x: x.get('metadata', {}).get('chunk_index', 0) 
                                        if isinstance(x.get('metadata'), dict) else 0
                                    )
                                    for insight in sorted_insights:
                                        if 'metadata' in insight and 'content' in insight:
                                            insights.append({
                                                'content': insight['content'],
                                                'metadata': insight['metadata']
                                            })
                                
                                if insights:
                                    doc['insights'] = insights
                                    logger.info(f"[_retrieve] Added {len(insights)} insights to document {doc_id}")
                            except Exception as e:
                                logger.warning(f"[_retrieve] Error getting insights from ChromaDB: {e}")

                            retrieved_docs.append(doc)
                            found_in_postgres = True
                            break
                    
                    # Step 2: If not found in PostgreSQL, try to find in ChromaDB collections
                    if not found_in_postgres:
                        logger.info(f"[_retrieve] Document {doc_id} not found in PostgreSQL, checking ChromaDB collections")
                        # Get all available collections
                        collections = chroma_db.list_collections()
                        collection_names = [collection.name for collection in collections]
                        
                        # Prioritize 'documents' collection for PDF lookup
                        if 'documents' in collection_names:
                            # Move 'documents' to the front of the list
                            collection_names.remove('documents')
                            collection_names.insert(0, 'documents')
                        
                        # Filter out the "extraction_questions" collection
                        collection_names = [name for name in collection_names if name != "extraction_questions"]
                        
                        # Try different ID formats (similar to document_handler.get_document_metadata_from_chromadb)
                        possible_ids = [
                            doc_id,               # Original ID
                            f"doc_{doc_id}",      # doc_ prefix
                        ]
                        
                        # Add phrase_id pattern formats 
                        phrase_ids = [f"phrase_{doc_id}_{i}" for i in range(10)]  # Try suffixes _0 through _9
                        possible_ids.extend(phrase_ids)
                        
                        # Add chunk pattern formats for PDF documents
                        chunk_ids = [f"{doc_id}-chunk-{i}" for i in range(10)]  # Try chunk suffixes 0-9
                        possible_ids.extend(chunk_ids)
                        
                        logger.info(f"[_retrieve] Trying {len(possible_ids)} possible ID formats in ChromaDB")
                        
                        # Variables to collect results from multiple chunks
                        all_metadata = {}
                        content_parts = []
                        found_ids = []
                        found_any = False
                        
                        # Try each collection with each possible ID format
                        for collection_name in collection_names:
                            # Try each ID format for this collection
                            for pid in possible_ids:
                                try:
                                    # Try to get the document directly by ID
                                    chroma_results = chroma_db.get_record(collection_name, pid)
                                    if chroma_results and chroma_results.get('ids') and len(chroma_results['ids']) > 0:
                                        found_any = True
                                        found_ids.append(pid)
                                        logger.info(f"[_retrieve] Found document with ID format {pid} in ChromaDB collection {collection_name}")
                                        
                                        # Extract content and metadata
                                        if "documents" in chroma_results and chroma_results["documents"] and len(chroma_results["documents"]) > 0:
                                            doc_content = chroma_results["documents"][0]
                                            if doc_content:
                                                content_parts.append(doc_content)
                                        
                                        if "metadatas" in chroma_results and chroma_results["metadatas"] and len(chroma_results["metadatas"]) > 0:
                                            doc_metadata = chroma_results["metadatas"][0]
                                            # Merge with existing metadata
                                            for key, value in doc_metadata.items():
                                                if key not in all_metadata:
                                                    all_metadata[key] = value
                                except Exception as ce:
                                    logger.warning(f"[_retrieve] Error searching for ID format {pid} in collection {collection_name}: {ce}")
                                    continue
                            
                            # If we haven't found anything by direct ID lookup, try metadata search
                            if not found_any:
                                try:
                                    # Try to query the collection for documents with matching metadata
                                    results = chroma_db.query_collection_with_relevance_scores(
                                        collection_name=collection_name,
                                        query_texts=[""],  # Empty query to get all documents
                                        n_results=25,
                                        where={"document_id": {"$eq": doc_id}}  # Look for metadata with matching document_id
                                    )
                                    
                                    if results and len(results) > 0:
                                        logger.info(f"[_retrieve] Found document {doc_id} via metadata in ChromaDB collection {collection_name}")
                                        # Process results to extract content and metadata
                                        for result in results:
                                            found_any = True
                                            # Add content if available
                                            if 'document' in result:
                                                content_parts.append(result['document'])
                                            # Add metadata
                                            if 'metadata' in result:
                                                for key, value in result['metadata'].items():
                                                    if key not in all_metadata:
                                                        all_metadata[key] = value
                                except Exception as ce:
                                    logger.warning(f"[_retrieve] Error querying collection {collection_name} for document {doc_id}: {ce}")
                                    continue
                        
                        # If we found the document in ChromaDB
                        if found_any:
                            # Combine content parts
                            combined_content = "\n\n".join(content_parts) if content_parts else ""
                            
                            # Get document type from metadata
                            doc_type = all_metadata.get('document_type')
                            if not doc_type:
                                logger.warning(f"[_retrieve] No document type found in metadata for document {doc_id}, skipping")
                                continue
                            
                            # Create a document record
                            doc = {
                                'document_id': doc_id,
                                'document_type': doc_type,
                                'content': combined_content,
                                'metadata': all_metadata,
                                'found_ids': found_ids,
                                'collection': collection_name,
                                'relevance_score': 1.0  # Assign maximum relevance as document was explicitly selected
                            }

                            # Try to get insights from the insights collection
                            try:
                                insights = []
                                # Query insights collection for this document
                                insight_results = chroma_db.query_collection_with_relevance_scores(
                                    collection_name="insights",
                                    query_texts=[""],  # Empty query to get all insights
                                    n_results=50,  # Increase to get all chunks' insights
                                    where={
                                        "$or": [
                                            {"parent_document_id": {"$eq": doc_id}},
                                            {"document_id": {"$eq": doc_id}}
                                        ]
                                    }
                                )
                                
                                if insight_results and len(insight_results) > 0:
                                    logger.info(f"[_retrieve] Found {len(insight_results)} insights for document {doc_id}")
                                    # Sort insights by chunk_index if available
                                    sorted_insights = sorted(
                                        insight_results,
                                        key=lambda x: x.get('metadata', {}).get('chunk_index', 0) 
                                        if isinstance(x.get('metadata'), dict) else 0
                                    )
                                    for insight in sorted_insights:
                                        if 'metadata' in insight and 'content' in insight:
                                            insights.append({
                                                'content': insight['content'],
                                                'metadata': insight['metadata']
                                            })
                                
                                if insights:
                                    doc['insights'] = insights
                                    logger.info(f"[_retrieve] Added {len(insights)} insights to document {doc_id}")
                            except Exception as e:
                                logger.warning(f"[_retrieve] Error getting insights from ChromaDB: {e}")

                            retrieved_docs.append(doc)
                            found_in_postgres = True  # Mark as found to prevent further searching
                                    
                    if not found_in_postgres:
                        logger.warning(f"[_retrieve] Document ID {doc_id} not found in any known collections (PostgreSQL or ChromaDB)")
                except Exception as e:
                    logger.error(f"[_retrieve] Error retrieving document {doc_id}: {e}")
            
            logger.info(f"[_retrieve] Retrieved {len(retrieved_docs)} documents from specified IDs")
            state.retrieved_documents = retrieved_docs
            return state
        
        # Regular retrieval process when no specific document IDs are provided
        # Use get_documents_query to search across the documents collection with time-based filtering
        logger.info(f"[_retrieve] Searching entire documents collection with time-based filtering (last 120 days)")
        retrieved_docs = get_documents_query(
            query=query,
            n_results=25
        )
        
        # Add debug logging
        logger.info(f"[_retrieve] Retrieved {len(retrieved_docs)} documents from query: {query}")
        if retrieved_docs:
            collections_found = set(doc.get('collection', 'unknown') for doc in retrieved_docs)
            logger.info(f"[_retrieve] Documents found in collections: {collections_found}")
            for i, doc in enumerate(retrieved_docs[:5]):  # Log the first 5 documents
                logger.info(f"[_retrieve] Document {i+1}: ID={doc.get('document_id', 'unknown')}, Type={doc.get('document_type', 'unknown')}, Score={doc.get('relevance_score', 0)}")
        else:
            logger.warning("[_retrieve] No documents found for the query")
            # Simply retry without time filter if no documents found
            logger.info(f"[_retrieve] Falling back to unfiltered search (without time filter)")
            retrieved_docs = get_documents_query(
                query=query,
                n_results=25
            )
        
        state.retrieved_documents = retrieved_docs
        return state
    
    async def _analyze_retrieval(self, state: SelfRAGState) -> SelfRAGState:
        """Analyze the retrieval results to determine if they're relevant."""
        logger.info("[_analyze_retrieval] Starting retrieval analysis")
        
        # If specific document IDs are provided, skip relevance analysis
        if state.document_ids:
            logger.info("[_analyze_retrieval] Using specific document IDs, assuming relevance")
            state.reflection = "Using specifically requested documents, relevance is assumed."
            return state
        
        system_prompt = """You are an expert document analyst.
        You need to evaluate if the retrieved documents are relevant to the user's question.
        Analyze the list of document metadata and decide if they seem relevant or if we need to reformulate the query.
        
        Your output should be a JSON with the following structure:
        {
            "relevant": true/false,
            "reasoning": "Your reasoning here"
        }
        """
        
        # Prepare the relevant context
        context = {
            "question": state.question,
            "retrieved_documents": state.retrieved_documents,
            "query": state.current_query,
            "query_type": state.query_type,
            "source_type": state.source
        }
        
        try:
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
            logger.info("[_analyze_retrieval] Analyzing retrieval results with LLM")
            analysis_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Here is the context:\n{context}\n\nAnalyze if these documents are relevant to the question.")
                ]
            )
            
            logger.info(f"[_analyze_retrieval] Analysis response received: {analysis_response.content[:100]}...")
            
            # Extract JSON from the response
            if isinstance(analysis_response.content, str):
                json_match = re.search(r'{.*}', analysis_response.content, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    state.reflection = analysis.get("reasoning", "")
                    logger.info(f"[_analyze_retrieval] Analysis result: {analysis}")
                    return state
            
            logger.error("[_analyze_retrieval] Failed to extract JSON from analysis response")
            state.reflection = "Failed to analyze retrieval results properly."
            return state
                
        except Exception as e:
            logger.error(f"[_analyze_retrieval] Error analyzing retrieval: {e}")
            state.reflection = f"Error analyzing retrieval: {str(e)}"
            return state
    
    async def _retrieve_full_documents(self, state: SelfRAGState) -> SelfRAGState:
        """Retrieve the full content of the most relevant documents."""
        logger.info(f"Retrieving full document content for {len(state.retrieved_documents)} documents")
        selected_docs = []
        
        # Get the top 3 documents (or all documents if we're using specific document IDs)
        n_docs = len(state.retrieved_documents) if state.document_ids else 25
        top_docs = state.retrieved_documents[:n_docs] if state.retrieved_documents else []
        
        if not top_docs:
            logger.warning("No documents available to retrieve full content")
            return state
            
        for i, doc in enumerate(top_docs):
            try:
                # Get document_type from the document if it exists
                doc_type = doc.get('document_type', 'generic')
                doc_id = doc.get('document_id', '')
                collection = doc.get('collection', '')
                
                logger.info(f"Retrieving full content for document {i+1}/{len(top_docs)}: ID={doc_id}, Type={doc_type}, Collection={collection}")
                
                # If we already have content, use it directly instead of fetching
                if 'content' in doc and doc['content']:
                    logger.info(f"Using existing content for document {doc_id}")
                    content = doc['content']
                    # Convert content to dict if it's a string
                    if isinstance(content, str):
                        content = {"text": content}
                    elif not isinstance(content, dict):
                        # Try to convert to dict if possible
                        try:
                            content = {"data": str(content)}
                        except:
                            content = {"text": "Content format not supported"}
                            
                    full_doc = RetrievedDocument(
                        document_id=doc_id,
                        document_type=doc_type,
                        content=content,
                        relevance_score=doc.get('relevance_score', 0.0),
                        metadata=doc.get('metadata', {}),
                        insights=doc.get('insights', [])
                    )
                    selected_docs.append(full_doc)
                    continue
                
                # Otherwise try to fetch from database
                logger.info(f"Fetching document {doc_id} from database")
                postgres_db = PostgresDB()
                record = postgres_db.get_record(f"document_{doc_type}", doc_id)
                
                if record:
                    logger.info(f"Successfully retrieved document {doc_id} from database")
                    full_doc = RetrievedDocument(
                        document_id=doc_id,
                        document_type=doc_type,
                        content=record,
                        relevance_score=doc.get('relevance_score', 0.0),
                        metadata=doc.get('metadata', {}),
                        insights=doc.get('insights', [])
                    )
                    selected_docs.append(full_doc)
                else:
                    logger.warning(f"Document {doc_id} not found in database")
                    
            except Exception as e:
                logger.error(f"Error retrieving full document {doc.get('document_id', 'unknown')}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Update state with the selected documents
        logger.info(f"Retrieved {len(selected_docs)} full documents")
        state.selected_documents = selected_docs
        return state
    
    def _needs_sfdc_data(self, state: SelfRAGState) -> bool:
        """Determine if SFDC data is needed based on the documents and query."""
        # Check if we have any Salesforce-related keywords in the question
        sfdc_keywords = ["opportunity", "deal", "sales", "pipeline", "forecast", 
                        "revenue", "salesforce", "account", "close date", "account","lead","activity","task","contact","associate","sales rep"]
                        
        question_lower = state.question.lower()
        
        for keyword in sfdc_keywords:
            if keyword in question_lower:
                return True
                
        # Check if we have Gong transcripts that might reference Salesforce data
        for doc in state.selected_documents:
            content = str(doc.content).lower()
            for keyword in ["opportunity", "deal", "pipeline", "revenue"]:
                if keyword in content:
                    return True
                        
        return False
    
    async def _get_sfdc_table_schema(self, state: SelfRAGState) -> SelfRAGState:
        """Get the Salesforce table schema for the query."""
        system_prompt = """You are an expert at Salesforce data modeling.
        You need to provide the tables based on schema for the Salesforce objects that is most relevant to the user's question.
        You will be given a list of tables and their schemas that are supported by the sfdc_context_store.
        {sfdc_tables}
        You will also be given a user question and a list of documents that are relevant to the question.
        Your output should be a simple comma-separated list of table names (no quotes, spaces or additional formatting).
        Example correct output: "Opportunity,Account,Contact"
        """
        doc_context = state.context
        sfdc_tables = get_sfdc_tables()
        system_prompt = system_prompt.format(sfdc_tables=sfdc_tables)

        try:
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
            table_schema = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"User question: {state.question}\n\nDocument context: {doc_context}\n\nProvide comma-separated list of relevant tables:")
                ]
            ) 
            
            tables_list = []
            if isinstance(table_schema.content, str):
                # Clean and process the table names
                content = table_schema.content.strip()
                logger.info(f"Raw LLM response for tables: {content}")
                
                # Remove any markdown formatting or quotes that might be present
                clean_content = content
                # Remove code block markers if present
                if "```" in clean_content:
                    import re
                    clean_content = re.sub(r'```.*?```', '', clean_content, flags=re.DOTALL)
                    clean_content = re.sub(r'```.*?$', '', clean_content, flags=re.DOTALL)
                
                # Split by comma and clean each table name
                raw_tables = [t.strip().strip('"\'`').strip() for t in clean_content.split(',')]
                logger.info(f"Parsed table names: {raw_tables}")
                
                # Filter out empty strings
                tables_list = [t for t in raw_tables if t]
                
                # If no valid tables, default to Opportunity
                if not tables_list:
                    logger.warning("No valid table names found in response, defaulting to Opportunity")
                    tables_list = ["salesforce_opportunities"]
                    
                logger.info(f"Final table list: {tables_list}")
            else:
                logger.warning("Table schema response content is not a string")
                tables_list = ["salesforce_opportunities"]  # Default
                
            state.sfdc_tables = tables_list
            return state
        except Exception as e:
            logger.error(f"Error getting SFDC table schema: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            state.sfdc_tables = ["salesforce_opportunities"]  # Default to Opportunity if there's an error
            return state
        
    async def _query_sfdc(self, state: SelfRAGState) -> SelfRAGState:
        """Generate and execute a SFDC query based on the documents and question."""
        try:
            # Validate and clean sfdc_tables
            if not state.sfdc_tables or not isinstance(state.sfdc_tables, list):
                logger.warning(f"Invalid sfdc_tables: {state.sfdc_tables}. Using default Opportunity table.")
                state.sfdc_tables = ["salesforce_opportunities"]
            
            # Filter out any tables that are not in our allowed list
            allowed_tables = ["salesforce_opportunities", "salesforce_accounts"]
            state.sfdc_tables = [table for table in state.sfdc_tables if table in allowed_tables]
            
            # If no valid tables remain, default to Opportunity
            if not state.sfdc_tables:
                logger.warning("No valid tables in filtered list. Using default Opportunity table.")
                state.sfdc_tables = ["salesforce_opportunities"]
            
            # Get table schemas
            logger.info(f"Getting table schemas for: {state.sfdc_tables}")
            sfdc_tables = get_sfdc_tables_prompt_bykey(state.sfdc_tables)
            
            system_prompt = """You are an expert at SQL query generation for Salesforce data.
            Based on the user's question and the retrieved documents, generate a SQL query to retrieve relevant opportunity data.
            You will be given a list of tables and their schemas that are supported by the sfdc_context_store.
            {sfdc_tables}
            Generate ONLY a SQL SELECT query against each individual table.
            The response should be a list of valid SQL queries separated by ':' as string. Do not put a semicolon at the end of the query.
            please use the table names as they are in the sfdc_tables list.

            FORMATTING RULES:
            1. Return ONLY the SQL query without any table name prefix or JSON formatting
            2. Do not include quotes around the query
            3. Do not include any table name as a key or prefix
            4. Example correct format: SELECT * FROM salesforce_opportunities LIMIT 5
            5. Example incorrect format: "salesforce_opportunities": "SELECT * FROM salesforce_opportunities LIMIT 5"
            """
            
            system_prompt = system_prompt.format(sfdc_tables=sfdc_tables)
            # Prepare context from documents
            doc_context = []
            for doc in state.selected_documents:
                # Extract relevant fields for context
                if doc.document_type == "GONG_TRANSCRIPT":
                    # If there's an opportunity ID or account ID in the transcript, include it
                    content = str(doc.content)
                    doc_context.append(f"Transcript ID: {doc.document_id}")
                    
                    # Try to extract any opportunity or account references
                    opp_ids = re.findall(r'opportunity[_\s]?id[:\s]+([a-zA-Z0-9]+)', content, re.IGNORECASE)
                    account_ids = re.findall(r'account[_\s]?id[:\s]+([a-zA-Z0-9]+)', content, re.IGNORECASE)
                    
                    if opp_ids:
                        doc_context.append(f"Referenced opportunity IDs: {', '.join(opp_ids)}")
                    if account_ids:
                        doc_context.append(f"Referenced account IDs: {', '.join(account_ids)}")
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
            logger.info(f"Generating SQL query for question: {state.question}")
            query_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"User question: {state.question}\n\nDocument context: {doc_context}\n\nGenerate a SQL query to get relevant opportunities:")
                ]
            )
            
            # Extract the SQL query
            sql_query = ""
            if isinstance(query_response.content, str):
                query_match = re.search(r'```sql\s*(.*?)\s*```', query_response.content, re.DOTALL)
                if query_match:
                    sql_query = query_match.group(1).strip()
                else:
                    sql_query = query_response.content.strip()
                    
                logger.info(f"Generated SQL query: {sql_query}")
                print(f"Generated SQL query: {sql_query}")
                
                # Execute the query
                try:
                    postgres_db = PostgresDB()
                    
                    # Security check: Ensure only SELECT queries against sfdc_opportunities table
                    if not sql_query.strip().lower().startswith("select"):
                        raise ValueError("Only SELECT queries are allowed")

                    # Security check: Ensure the query only targets allowed tables
                    query_lower = sql_query.lower()
                    if not any(table in query_lower for table in allowed_tables):
                        raise ValueError(f"Query must target one of these tables: {allowed_tables}")

                    # Security check: Ensure no dangerous SQL operations
                    dangerous_keywords = [
                        "insert", "update", "delete", "drop", "alter",
                        "create", "truncate", "replace", "merge"
                    ]
                    for keyword in dangerous_keywords:
                        if keyword in sql_query.lower():
                            raise ValueError(f"Operation '{keyword}' is not allowed")

                    # Add limit if not present
                    if "limit" not in sql_query.lower():
                        sql_query += " LIMIT 5"

                    # Execute the query
                    logger.info(f"Executing SQL query: {sql_query}")
                    results = postgres_db.execute_query(sql_query)
                    logger.info(f"Query returned {len(results)} results")
                    state.sfdc_query_results = results
                    
                except Exception as e:
                    logger.error(f"Error executing SFDC query: {e}")
                    state.sfdc_query_results = []
            else:
                logger.warning("Query response content is not a string")
                
        except Exception as e:
            logger.error(f"Error in _query_sfdc: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            state.sfdc_query_results = []
            
        return state
    
    async def _generate_answer(self, state: SelfRAGState) -> SelfRAGState:
        """Generate an answer based on the retrieved documents and SFDC data."""
        system_prompt = """You are a helpful document analyst that performs research on corporate marketing documents.
        You are very thorough and specific in your answers. You will cite sources in your response.
        
        Based on the retrieved documents, metadata, insights, and data, provide a comprehensive answer to the user's question.
        Pay special attention to:
        1. Document metadata which may contain important information about the document's source, author, creation date, and other attributes
        2. Document insights which may contain pre-extracted key information and analysis
        3. Document content for detailed information
        
        When referencing specific documents, mention the document ID and type.
        When referencing metadata or insights, include the specific fields you used in your analysis.
        Format your response in markdown.
        """
        
        # Prepare the context
        document_context = []
        for doc in state.selected_documents:
            document_context.append(f"--- Document ID: {doc.document_id} ---")
            document_context.append(f"Type: {doc.document_type}")
            document_context.append(f"Content: {doc.content}")
            
            # Include insights if available
            if hasattr(doc, 'insights') and doc.insights:
                document_context.append(f"Insights:")
                for insight in doc.insights:
                    document_context.append(f"  - {insight.get('content', '')}")
                    if 'metadata' in insight:
                        document_context.append(f"    Metadata: {insight['metadata']}")
            
            # Include metadata in the context if available
            if doc.metadata and len(doc.metadata) > 0:
                document_context.append(f"Metadata:")
                for key, value in doc.metadata.items():
                    # Format each metadata item for readability
                    if key not in ["content", "text"]:  # Skip content duplicates
                        document_context.append(f"  - {key}: {value}")
            
            document_context.append("")
        
        sfdc_context = []
        if state.sfdc_query_results:
            sfdc_context.append("--- Salesforce Opportunities ---")
            for i, opp in enumerate(state.sfdc_query_results):
                sfdc_context.append(f"Opportunity {i+1}: {opp}")
            sfdc_context.append("")
        
        context = "\n".join(document_context + sfdc_context)
        
        try:
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
            answer_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"User question: {state.question}\n\nContext:\n{context}\n\nPlease provide a comprehensive answer:")
                ]
            )
            
            if isinstance(answer_response.content, str):
                state.answer = answer_response.content
            else:
                logger.warning("Answer response content is not a string")
                state.answer = "I couldn't generate a proper answer based on the available information."
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            state.answer = f"I encountered an error while analyzing your documents. Please try again."
            
        return state
    
    async def _reflect(self, state: SelfRAGState) -> SelfRAGState:
        """Reflect on the answer to determine if it's complete and accurate."""
        system_prompt = """You are an expert at evaluating the quality of answers to user questions.
        Your task is to evaluate if the answer properly addresses the user's question and is supported by the available documents.
        
        Consider:
        1. Does the answer respond to all aspects of the question?
        2. Is the answer supported by the retrieved documents or does it require more information?
        3. Are there any inconsistencies or ambiguities in the answer?
        4. Does the answer properly cite the sources?
        
        Output a JSON with the following structure:
        {
            "sufficient": true/false,
            "reasoning": "Your detailed reasoning",
            "missing_info": "What information is missing if any"
        }
        """
        
        try:
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
            reflection_response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"User question: {state.question}\n\nGenerated answer: {state.answer}\n\nPlease evaluate:")
                ]
            )
            
            # Extract JSON from the response
            if isinstance(reflection_response.content, str):
                json_match = re.search(r'{.*}', reflection_response.content, re.DOTALL)
                if json_match:
                    reflection = json.loads(json_match.group(0))
                    state.reflection = reflection.get("reasoning", "")
                    state.needs_more_info = not reflection.get("sufficient", True)
                    return state
            
            logger.error("Failed to extract JSON from reflection response")
            state.reflection = "Failed to properly evaluate the answer."
            state.needs_more_info = False
                
        except Exception as e:
            logger.error(f"Error reflecting on answer: {e}")
            state.reflection = f"Error evaluating answer: {str(e)}"
            state.needs_more_info = False
            
        return state
    
    def _is_answer_sufficient(self, state: SelfRAGState) -> bool:
        """Determine if the answer is sufficient based on the reflection."""
        return not state.needs_more_info
    
    async def _finalize(self, state: SelfRAGState) -> SelfRAGState:
        """Finalize the answer, addressing any issues identified during reflection."""
        if state.needs_more_info:
            # This shouldn't happen, but just in case
            state.final_answer = state.answer + "\n\nNote: Some information might be missing or incomplete."
        else:
            # Format the answer with proper citations
            state.final_answer = state.answer
            
        return state