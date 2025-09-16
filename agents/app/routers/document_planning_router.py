import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime

# Import the document planning service
from app.services.docs.document_planning_service import DocumentPlanningService, DocumentPlanningResponse
from app.core.dependencies import get_app_state, get_doc_store_provider
from app.settings import get_settings
from app.services.service_container import SQLServiceContainer

logger = logging.getLogger(__name__)
settings = get_settings()

# Create router
router = APIRouter(prefix="/document-planning", tags=["document-planning"])

# Pydantic models for API requests/responses
class QuestionRequest(BaseModel):
    """Request model for question answering"""
    question: str = Field(..., description="The question to answer")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    source_type: Optional[str] = Field(None, description="Filter by source type")
    domain_id: Optional[str] = Field(None, description="Filter by domain ID")
    max_documents: int = Field(25, description="Maximum number of documents to retrieve")
    chat_history: Optional[List[Dict[str, Any]]] = Field(None, description="Optional conversation history")

class DocumentAnalysisRequest(BaseModel):
    """Request model for document analysis"""
    document_ids: List[str] = Field(..., description="List of document IDs to analyze")
    analysis_type: str = Field("comprehensive", description="Type of analysis to perform")

class SearchRequest(BaseModel):
    """Request model for document search"""
    query: str = Field(..., description="Search query")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    source_type: Optional[str] = Field(None, description="Filter by source type")
    domain_id: Optional[str] = Field(None, description="Filter by domain ID")
    max_documents: int = Field(10, description="Maximum number of documents to return")

class PlanningInsightsRequest(BaseModel):
    """Request model for planning insights"""
    question: str = Field(..., description="The question to analyze")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    source_type: Optional[str] = Field(None, description="Filter by source type")
    domain_id: Optional[str] = Field(None, description="Filter by domain ID")

class QuestionResponse(BaseModel):
    """Response model for question answering"""
    question: str
    reframed_question: str
    strategy: str
    confidence: float
    retrieval_grade: str
    documents_found: int
    execution_successful: bool
    final_answer: str
    execution_time: float
    plan_steps: List[Dict[str, Any]]
    retrieval_analysis: Dict[str, Any]
    recommendations: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)

class DocumentAnalysisResponse(BaseModel):
    """Response model for document analysis"""
    analysis_type: str
    documents_analyzed: int
    execution_successful: bool
    results: List[Dict[str, Any]]
    final_analysis: str
    timestamp: datetime = Field(default_factory=datetime.now)

class SearchResponse(BaseModel):
    """Response model for document search"""
    query: str
    total_found: int
    retrieval_grade: str
    documents: List[Dict[str, Any]]
    relevance_scores: List[float]
    coverage_analysis: Dict[str, Any]
    gaps_identified: List[str]
    recommendations: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)

class PlanningInsightsResponse(BaseModel):
    """Response model for planning insights"""
    question: str
    reframed_question: str
    recommended_strategy: str
    confidence: float
    retrieval_grade: str
    documents_available: int
    plan_steps: List[Dict[str, Any]]
    retrieval_analysis: Dict[str, Any]
    estimated_complexity: str
    suggested_improvements: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)

# Dependency to get document planning service
def get_document_planning_service(
    app_state = Depends(get_app_state),
    doc_store_provider = Depends(get_doc_store_provider)
) -> DocumentPlanningService:
    """Get document planning service instance from service container"""
    # Get the service container
    container = SQLServiceContainer.get_instance()
    
    # Get the document persistence service
    document_service = container.get_document_persistence_service()
    
    # Get the chroma store from document store provider
    chroma_store = doc_store_provider.get_store("document_planning")
    
    return DocumentPlanningService(
        document_service=document_service,
        chroma_store=chroma_store
    )

@router.post("/answer", response_model=QuestionResponse)
async def answer_question(
    request: QuestionRequest,
    service: DocumentPlanningService = Depends(get_document_planning_service)
):
    """
    Answer a question using document planning and execution
    
    This endpoint uses the enhanced document planner to:
    1. Retrieve relevant documents using docmodels
    2. Grade the retrieval quality
    3. Create an execution plan
    4. Execute the plan to generate an answer
    """
    try:
        logger.info(f"Answering question: {request.question}")
        
        response = await service.answer_question(
            question=request.question,
            document_type=request.document_type,
            source_type=request.source_type,
            domain_id=request.domain_id,
            max_documents=request.max_documents,
            chat_history=request.chat_history
        )
        
        return QuestionResponse(
            question=response.question,
            reframed_question=response.reframed_question,
            strategy=response.strategy.value,
            confidence=response.confidence,
            retrieval_grade=response.retrieval_grade.value,
            documents_found=response.documents_found,
            execution_successful=response.execution_successful,
            final_answer=response.final_answer,
            execution_time=response.execution_time,
            plan_steps=response.plan_steps,
            retrieval_analysis=response.retrieval_analysis,
            recommendations=response.recommendations
        )
        
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        raise HTTPException(status_code=500, detail=f"Error answering question: {str(e)}")

@router.post("/analyze-documents", response_model=DocumentAnalysisResponse)
async def analyze_documents(
    request: DocumentAnalysisRequest,
    service: DocumentPlanningService = Depends(get_document_planning_service)
):
    """
    Analyze specific documents using document planning
    
    This endpoint analyzes a set of documents using the document planning framework
    to extract insights, structured data, or perform comprehensive analysis.
    """
    try:
        logger.info(f"Analyzing {len(request.document_ids)} documents with type: {request.analysis_type}")
        
        response = await service.get_document_analysis(
            document_ids=request.document_ids,
            analysis_type=request.analysis_type
        )
        
        if "error" in response:
            raise HTTPException(status_code=400, detail=response["error"])
        
        return DocumentAnalysisResponse(
            analysis_type=response["analysis_type"],
            documents_analyzed=response["documents_analyzed"],
            execution_successful=response["execution_successful"],
            results=response["results"],
            final_analysis=response["final_analysis"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing documents: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing documents: {str(e)}")

@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    service: DocumentPlanningService = Depends(get_document_planning_service)
):
    """
    Search for documents using the document planning retrieval system
    
    This endpoint uses the enhanced document retrieval service to find relevant
    documents and provides detailed analysis of the retrieval quality.
    """
    try:
        logger.info(f"Searching documents with query: {request.query}")
        
        response = await service.search_documents(
            query=request.query,
            document_type=request.document_type,
            source_type=request.source_type,
            domain_id=request.domain_id,
            max_documents=request.max_documents
        )
        
        if "error" in response:
            raise HTTPException(status_code=400, detail=response["error"])
        
        return SearchResponse(
            query=response["query"],
            total_found=response["total_found"],
            retrieval_grade=response["retrieval_grade"],
            documents=response["documents"],
            relevance_scores=response["relevance_scores"],
            coverage_analysis=response["coverage_analysis"],
            gaps_identified=response["gaps_identified"],
            recommendations=response["recommendations"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching documents: {str(e)}")

@router.post("/planning-insights", response_model=PlanningInsightsResponse)
async def get_planning_insights(
    request: PlanningInsightsRequest,
    service: DocumentPlanningService = Depends(get_document_planning_service)
):
    """
    Get insights about how the planner would approach a question
    
    This endpoint analyzes a question and provides insights about:
    - Recommended planning strategy
    - Expected retrieval quality
    - Plan complexity
    - Suggested improvements
    """
    try:
        logger.info(f"Getting planning insights for question: {request.question}")
        
        response = await service.get_planning_insights(
            question=request.question,
            document_type=request.document_type,
            source_type=request.source_type,
            domain_id=request.domain_id
        )
        
        if "error" in response:
            raise HTTPException(status_code=400, detail=response["error"])
        
        return PlanningInsightsResponse(
            question=response["question"],
            reframed_question=response["reframed_question"],
            recommended_strategy=response["recommended_strategy"],
            confidence=response["confidence"],
            retrieval_grade=response["retrieval_grade"],
            documents_available=response["documents_available"],
            plan_steps=response["plan_steps"],
            retrieval_analysis=response["retrieval_analysis"],
            estimated_complexity=response["estimated_complexity"],
            suggested_improvements=response["suggested_improvements"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting planning insights: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting planning insights: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint for document planning service"""
    return {
        "status": "healthy",
        "service": "document-planning",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@router.get("/strategies")
async def get_available_strategies():
    """Get list of available planning strategies"""
    from app.agents.nodes.docs.enhanced_document_planner import DocumentPlanningStrategy
    
    strategies = [
        {
            "name": strategy.value,
            "description": _get_strategy_description(strategy)
        }
        for strategy in DocumentPlanningStrategy
    ]
    
    return {
        "strategies": strategies,
        "total_count": len(strategies)
    }

def _get_strategy_description(strategy) -> str:
    """Get description for a planning strategy"""
    descriptions = {
        "comprehensive_analysis": "Full document analysis with detailed insights",
        "focused_extraction": "Extract specific information from most relevant documents",
        "comparative_analysis": "Compare information across multiple documents",
        "timeline_analysis": "Time-based analysis of document content",
        "metadata_analysis": "Focus on document metadata and properties",
        "content_summarization": "Summarize document content for quick overview",
        "structured_extraction": "Extract structured data like tables and lists"
    }
    return descriptions.get(strategy.value, "Document analysis strategy")

@router.get("/retrieval-grades")
async def get_retrieval_grades():
    """Get list of available retrieval grades"""
    from app.agents.nodes.docs.enhanced_document_planner import RetrievalGrade
    
    grades = [
        {
            "name": grade.value,
            "description": _get_grade_description(grade)
        }
        for grade in RetrievalGrade
    ]
    
    return {
        "grades": grades,
        "total_count": len(grades)
    }

def _get_grade_description(grade) -> str:
    """Get description for a retrieval grade"""
    descriptions = {
        "excellent": "Highly relevant documents with comprehensive coverage",
        "good": "Relevant documents with some gaps in coverage",
        "fair": "Partially relevant documents with significant gaps",
        "poor": "Low relevance documents with major gaps",
        "insufficient": "No relevant documents found"
    }
    return descriptions.get(grade.value, "Document retrieval quality grade")

# Example usage endpoints
@router.get("/examples")
async def get_examples():
    """Get example requests for the document planning API"""
    return {
        "question_examples": [
            {
                "question": "What are the key financial metrics in the quarterly reports?",
                "document_type": "financial_report",
                "description": "Analyze financial documents for key metrics"
            },
            {
                "question": "Compare the performance metrics across different departments",
                "document_type": "performance_report",
                "description": "Comparative analysis of department performance"
            },
            {
                "question": "What are the main topics discussed in the meeting notes?",
                "document_type": "meeting_notes",
                "description": "Extract and summarize main topics from meeting notes"
            }
        ],
        "analysis_examples": [
            {
                "analysis_type": "comprehensive",
                "description": "Full document analysis with detailed insights"
            },
            {
                "analysis_type": "structured",
                "description": "Extract structured data like tables and lists"
            },
            {
                "analysis_type": "summary",
                "description": "Generate document summaries"
            }
        ],
        "search_examples": [
            {
                "query": "revenue growth",
                "document_type": "financial_report",
                "description": "Search for revenue growth information"
            },
            {
                "query": "customer feedback",
                "document_type": "survey",
                "description": "Search for customer feedback data"
            }
        ]
    }
