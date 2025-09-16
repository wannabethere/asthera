import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime

# Import the enhanced self-rag agent
from app.agents.nodes.docs.enhanced_self_rag_agent import EnhancedSelfRAGAgent
from app.services.docs.document_schemas import DocumentType
from app.core.dependencies import get_app_state, get_doc_store_provider
from app.settings import get_settings
from app.services.service_container import SQLServiceContainer

logger = logging.getLogger(__name__)
settings = get_settings()

# Create router
router = APIRouter(prefix="/enhanced-rag", tags=["enhanced-rag"])

# Pydantic models for API requests/responses
class EnhancedRAGRequest(BaseModel):
    """Request model for enhanced RAG"""
    question: str = Field(..., description="The question to answer")
    source_type: str = Field("generic", description="Type of documents to search")
    document_ids: Optional[List[str]] = Field(None, description="Specific document IDs to use")
    chat_history: Optional[List[Dict[str, Any]]] = Field(None, description="Optional conversation history")
    enable_web_search: bool = Field(True, description="Enable web search fallback")
    enable_tfidf: bool = Field(True, description="Enable TF-IDF ranking")
    max_documents: int = Field(25, description="Maximum number of documents to retrieve")

class EnhancedRAGResponse(BaseModel):
    """Response model for enhanced RAG"""
    question: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time: float
    action_taken: str = ""
    confidence: float = 0.0
    sources_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)

class ChatRequest(BaseModel):
    """Request model for chat conversation"""
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    source_type: str = Field("generic", description="Type of documents to search")
    enable_web_search: bool = Field(True, description="Enable web search fallback")

class ChatResponse(BaseModel):
    """Response model for chat conversation"""
    message: str
    conversation_id: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

# Dependency to get enhanced RAG agent
def get_enhanced_rag_agent(
    app_state = Depends(get_app_state),
    doc_store_provider = Depends(get_doc_store_provider)
) -> EnhancedSelfRAGAgent:
    """Get enhanced RAG agent instance from service container"""
    # The EnhancedSelfRAGAgent initializes its own DocumentChromaStore internally
    # We get the doc_store_provider for consistency but the agent manages its own store
    return EnhancedSelfRAGAgent()

@router.post("/ask", response_model=EnhancedRAGResponse)
async def ask_question(
    request: EnhancedRAGRequest,
    agent: EnhancedSelfRAGAgent = Depends(get_enhanced_rag_agent)
):
    """
    Ask a question using the enhanced Self-RAG agent
    
    This endpoint uses the enhanced Self-RAG agent with:
    - Document planning integration
    - TF-IDF ranking for better relevance
    - Tavily web search as fallback
    - Enhanced summarization with metadata
    """
    try:
        logger.info(f"Processing enhanced RAG question: {request.question}")
        
        # Convert source_type string to DocumentType enum
        try:
            source_type = DocumentType(request.source_type.lower())
        except ValueError:
            source_type = DocumentType.GENERIC
        
        # Run the enhanced agent
        start_time = datetime.now()
        
        response = await agent.run_agent(
            messages=request.chat_history or [],
            question=request.question,
            source_type=source_type,
            document_ids=request.document_ids
        )
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Extract response data
        if 'messages' in response and response['messages']:
            message = response['messages'][0]
            answer = message['message_content']
            
            # Extract metadata
            metadata = message.get('message_extra', {})
            action_taken = metadata.get('action_taken', '')
            sources_count = metadata.get('sources_count', 0)
            confidence = metadata.get('metadata', {}).get('confidence', 0.0)
            
            # Extract sources from answer if present
            sources = []
            if 'sources' in answer:
                try:
                    import re
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', answer, re.DOTALL)
                    if json_match:
                        import json
                        sources_data = json.loads(json_match.group(1))
                        sources = sources_data.get('sources', [])
                except Exception as e:
                    logger.warning(f"Error parsing sources from response: {e}")
            
            return EnhancedRAGResponse(
                question=request.question,
                answer=answer,
                sources=sources,
                metadata=metadata.get('metadata', {}),
                execution_time=execution_time,
                action_taken=action_taken,
                confidence=confidence,
                sources_count=sources_count
            )
        else:
            raise HTTPException(status_code=500, detail="No response generated by agent")
            
    except Exception as e:
        logger.error(f"Error processing enhanced RAG question: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: EnhancedSelfRAGAgent = Depends(get_enhanced_rag_agent)
):
    """
    Chat with the enhanced Self-RAG agent
    
    This endpoint maintains conversation context and provides
    enhanced responses with document planning and web search.
    """
    try:
        logger.info(f"Processing chat message: {request.message}")
        
        # Convert source_type string to DocumentType enum
        try:
            source_type = DocumentType(request.source_type.lower())
        except ValueError:
            source_type = DocumentType.GENERIC
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or f"chat_{int(datetime.now().timestamp())}"
        
        # For this example, we'll use empty chat history
        # In a real implementation, you'd store and retrieve chat history by conversation_id
        chat_history = []
        
        # Run the enhanced agent
        response = await agent.run_agent(
            messages=chat_history,
            question=request.message,
            source_type=source_type
        )
        
        # Extract response data
        if 'messages' in response and response['messages']:
            message = response['messages'][0]
            answer = message['message_content']
            
            # Extract metadata
            metadata = message.get('message_extra', {})
            
            # Extract sources
            sources = []
            if 'sources' in answer:
                try:
                    import re
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', answer, re.DOTALL)
                    if json_match:
                        import json
                        sources_data = json.loads(json_match.group(1))
                        sources = sources_data.get('sources', [])
                except Exception as e:
                    logger.warning(f"Error parsing sources from response: {e}")
            
            return ChatResponse(
                message=answer,
                conversation_id=conversation_id,
                sources=sources,
                metadata=metadata.get('metadata', {})
            )
        else:
            raise HTTPException(status_code=500, detail="No response generated by agent")
            
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint for enhanced RAG service"""
    return {
        "status": "healthy",
        "service": "enhanced-rag",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "features": [
            "document_planning",
            "tfidf_ranking", 
            "web_search_fallback",
            "enhanced_summarization",
            "metadata_extraction"
        ]
    }

@router.get("/capabilities")
async def get_capabilities():
    """Get capabilities of the enhanced RAG service"""
    return {
        "service": "enhanced-rag",
        "capabilities": {
            "document_planning": {
                "description": "Intelligent document retrieval planning",
                "strategies": [
                    "comprehensive_analysis",
                    "focused_extraction", 
                    "comparative_analysis",
                    "timeline_analysis",
                    "metadata_analysis",
                    "content_summarization",
                    "structured_extraction"
                ]
            },
            "tfidf_ranking": {
                "description": "TF-IDF based document relevance ranking",
                "features": [
                    "semantic_similarity",
                    "keyword_relevance",
                    "combined_scoring"
                ]
            },
            "web_search": {
                "description": "Tavily web search as fallback",
                "features": [
                    "external_source_integration",
                    "relevance_scoring",
                    "content_extraction"
                ]
            },
            "enhanced_summarization": {
                "description": "Advanced summarization with metadata",
                "features": [
                    "structured_output",
                    "source_citations",
                    "confidence_scoring",
                    "metadata_analysis"
                ]
            }
        },
        "supported_document_types": [
            "generic",
            "gong_transcript",
            "financial_report",
            "meeting_notes",
            "performance_report"
        ],
        "note": "This agent focuses on document search and analysis. For database queries, use dedicated SQL agents.",
        "api_endpoints": [
            "/ask - Ask a single question",
            "/chat - Multi-turn conversation",
            "/health - Service health check",
            "/capabilities - Service capabilities"
        ]
    }

@router.get("/examples")
async def get_examples():
    """Get example requests for the enhanced RAG API"""
    return {
        "ask_examples": [
            {
                "question": "What are the key financial metrics in our quarterly reports?",
                "source_type": "generic",
                "description": "Document planning with financial analysis"
            },
            {
                "question": "How has our sales performance changed over the last quarter?",
                "source_type": "generic", 
                "description": "Document analysis with performance metrics"
            },
            {
                "question": "What are the latest trends in AI for enterprise applications?",
                "source_type": "generic",
                "description": "Web search fallback for external information"
            }
        ],
        "chat_examples": [
            {
                "message": "What are our main revenue streams?",
                "description": "Start of conversation about revenue"
            },
            {
                "message": "How has SaaS revenue changed over time?",
                "description": "Follow-up question with context"
            },
            {
                "message": "What external factors might be affecting our growth?",
                "description": "Complex question requiring multiple sources"
            }
        ],
        "configuration_options": {
            "enable_web_search": "Enable/disable Tavily web search fallback",
            "enable_tfidf": "Enable/disable TF-IDF ranking",
            "max_documents": "Maximum number of documents to retrieve",
            "document_ids": "Specific document IDs to use"
        }
    }

@router.post("/test")
async def test_enhanced_rag(
    agent: EnhancedSelfRAGAgent = Depends(get_enhanced_rag_agent)
):
    """Test endpoint for enhanced RAG functionality"""
    try:
        # Run a simple test
        test_question = "What is artificial intelligence?"
        
        response = await agent.run_agent(
            messages=[],
            question=test_question,
            source_type=DocumentType.GENERIC
        )
        
        return {
            "status": "success",
            "test_question": test_question,
            "response_generated": 'messages' in response and len(response['messages']) > 0,
            "response_preview": response['messages'][0]['message_content'][:200] if 'messages' in response and response['messages'] else "No response",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
