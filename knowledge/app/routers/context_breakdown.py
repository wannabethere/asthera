"""
Context Breakdown Router
Provides streaming and non-streaming endpoints for context breakdown agents
"""
import logging
import uuid
from typing import Optional, List, Dict, Any, AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio

from app.agents.contextual_agents.context_breakdown_planner import ContextBreakdownPlanner
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent
from app.agents.contextual_agents.compliance_context_breakdown_agent import ComplianceContextBreakdownAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/context", tags=["Context Breakdown"])


# Request/Response Models
class ContextBreakdownRequest(BaseModel):
    """Request for context breakdown"""
    question: str = Field(..., description="User question to analyze")
    domain: Optional[str] = Field(None, description="Domain hint: 'mdl', 'compliance', or 'auto' (default)")
    product_name: Optional[str] = Field(None, description="Product name (for MDL queries)")
    frameworks: Optional[List[str]] = Field(None, description="Frameworks (for compliance queries)")
    available_products: Optional[List[str]] = Field(None, description="Available products")
    available_actors: Optional[List[str]] = Field(None, description="Available actor types")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    

class SearchQuestion(BaseModel):
    """Individual search question"""
    entity: str
    question: str
    metadata_filters: Dict[str, Any] = Field(default_factory=dict)
    response_type: Optional[str] = None


class ContextBreakdownResponse(BaseModel):
    """Response from context breakdown"""
    session_id: str
    query_type: str
    domains_involved: List[str]
    product_context: Optional[str] = None
    compliance_context: Optional[str] = None
    identified_entities: List[str] = Field(default_factory=list)
    entity_types: List[str] = Field(default_factory=list)
    edge_types: List[str] = Field(default_factory=list)
    search_questions: List[SearchQuestion] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    evidence_gathering_required: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextBreakdownSummary(BaseModel):
    """Summary response"""
    session_id: str
    query_type: str
    domains_involved: List[str]
    total_entities: int
    total_search_questions: int
    collections_to_query: List[str]
    summary: str


# Helper Functions
def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format SSE event"""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def stream_breakdown_progress(
    question: str,
    agent,
    domain: str,
    **kwargs
) -> AsyncGenerator[str, None]:
    """Stream breakdown progress"""
    session_id = kwargs.get("session_id", str(uuid.uuid4()))
    
    # Send start event
    yield format_sse_event("breakdown_started", {
        "session_id": session_id,
        "domain": domain,
        "question": question
    })
    
    try:
        # Send analyzing event
        yield format_sse_event("analyzing", {
            "session_id": session_id,
            "status": "Analyzing question...",
            "progress": 0.3
        })
        
        # Execute breakdown
        if isinstance(agent, ContextBreakdownPlanner):
            result = await agent.breakdown_question(question, **kwargs)
            breakdown = result.get("combined_breakdown")
            plan = result.get("plan", {})
            domains_used = []
            if plan.get("use_mdl"):
                domains_used.append("mdl")
            if plan.get("use_compliance"):
                domains_used.append("compliance")
        elif isinstance(agent, MDLContextBreakdownAgent):
            breakdown = await agent.breakdown_mdl_question(question, **kwargs)
            domains_used = ["mdl"]
        elif isinstance(agent, ComplianceContextBreakdownAgent):
            breakdown = await agent.breakdown_question(question, **kwargs)
            domains_used = ["compliance"]
        else:
            raise ValueError(f"Unknown agent type: {type(agent)}")
        
        # Send breakdown complete event
        yield format_sse_event("breakdown_complete", {
            "session_id": session_id,
            "status": "Breakdown complete",
            "progress": 0.8
        })
        
        # Send search questions event
        search_questions = []
        for sq in breakdown.search_questions:
            search_questions.append({
                "entity": sq.get("entity", ""),
                "question": sq.get("question", ""),
                "metadata_filters": sq.get("metadata_filters", {}),
                "response_type": sq.get("response_type", "")
            })
        
        yield format_sse_event("search_questions", {
            "session_id": session_id,
            "count": len(search_questions),
            "search_questions": search_questions
        })
        
        # Send result event
        collections = list(set(sq.get("entity", "") for sq in breakdown.search_questions))
        
        yield format_sse_event("result", {
            "session_id": session_id,
            "query_type": breakdown.query_type,
            "domains_involved": domains_used,
            "product_context": breakdown.product_context,
            "compliance_context": breakdown.compliance_context,
            "identified_entities": breakdown.identified_entities,
            "entity_types": breakdown.entity_types,
            "edge_types": breakdown.edge_types,
            "search_questions": search_questions,
            "frameworks": breakdown.frameworks,
            "evidence_gathering_required": breakdown.evidence_gathering_required,
            "collections_to_query": collections,
            "metadata": breakdown.metadata if hasattr(breakdown, 'metadata') else {}
        })
        
        # Send complete event
        yield format_sse_event("complete", {
            "session_id": session_id,
            "status": "Complete",
            "progress": 1.0
        })
        
    except Exception as e:
        logger.error(f"Error in breakdown: {e}", exc_info=True)
        yield format_sse_event("error", {
            "session_id": session_id,
            "error": str(e),
            "error_type": type(e).__name__
        })


# Endpoints
@router.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "router": "context_breakdown",
        "available_agents": ["mdl", "compliance", "planner"]
    }


@router.post("/breakdown/stream")
async def breakdown_stream(request: ContextBreakdownRequest):
    """
    Stream context breakdown analysis
    
    Returns SSE stream with:
    - breakdown_started: Analysis begins
    - analyzing: Progress update
    - breakdown_complete: Breakdown finished
    - search_questions: Generated search questions
    - result: Final breakdown result
    - complete: Stream complete
    - error: Error occurred
    """
    logger.info(f"Breakdown stream request: domain={request.domain}, question_length={len(request.question)}")
    
    # Determine which agent to use
    domain = request.domain or "auto"
    
    if domain == "mdl":
        agent = MDLContextBreakdownAgent()
        kwargs = {
            "product_name": request.product_name,
            "available_products": request.available_products,
            "session_id": request.session_id
        }
    elif domain == "compliance":
        agent = ComplianceContextBreakdownAgent()
        kwargs = {
            "available_frameworks": request.frameworks,
            "available_actors": request.available_actors,
            "session_id": request.session_id
        }
    else:  # auto
        agent = ContextBreakdownPlanner()
        kwargs = {
            "product_name": request.product_name,
            "available_frameworks": request.frameworks,
            "available_products": request.available_products,
            "available_actors": request.available_actors,
            "session_id": request.session_id
        }
    
    async def event_stream():
        async for event in stream_breakdown_progress(
            question=request.question,
            agent=agent,
            domain=domain,
            **kwargs
        ):
            yield event
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/breakdown", response_model=ContextBreakdownResponse)
async def breakdown(request: ContextBreakdownRequest):
    """
    Analyze user question and return context breakdown (non-streaming)
    
    Returns complete breakdown with:
    - Identified entities
    - Entity types and edge types
    - Generated search questions with filters
    - Domain detection (MDL, Compliance, or both)
    - Evidence gathering requirements
    """
    logger.info(f"Breakdown request: domain={request.domain}, question_length={len(request.question)}")
    
    try:
        session_id = request.session_id or str(uuid.uuid4())
        domain = request.domain or "auto"
        
        # Determine which agent to use and execute
        if domain == "mdl":
            agent = MDLContextBreakdownAgent()
            breakdown = await agent.breakdown_mdl_question(
                user_question=request.question,
                product_name=request.product_name,
                available_products=request.available_products
            )
            domains_used = ["mdl"]
            
        elif domain == "compliance":
            agent = ComplianceContextBreakdownAgent()
            breakdown = await agent.breakdown_question(
                user_question=request.question,
                available_frameworks=request.frameworks,
                available_actors=request.available_actors
            )
            domains_used = ["compliance"]
            
        else:  # auto
            planner = ContextBreakdownPlanner()
            result = await planner.breakdown_question(
                user_question=request.question,
                product_name=request.product_name,
                available_frameworks=request.frameworks,
                available_products=request.available_products,
                available_actors=request.available_actors
            )
            breakdown = result.get("combined_breakdown")
            plan = result.get("plan", {})
            domains_used = []
            if plan.get("use_mdl"):
                domains_used.append("mdl")
            if plan.get("use_compliance"):
                domains_used.append("compliance")
        
        # Format search questions
        search_questions = []
        for sq in breakdown.search_questions:
            search_questions.append(SearchQuestion(
                entity=sq.get("entity", ""),
                question=sq.get("question", ""),
                metadata_filters=sq.get("metadata_filters", {}),
                response_type=sq.get("response_type", "")
            ))
        
        return ContextBreakdownResponse(
            session_id=session_id,
            query_type=breakdown.query_type,
            domains_involved=domains_used,
            product_context=breakdown.product_context,
            compliance_context=breakdown.compliance_context,
            identified_entities=breakdown.identified_entities,
            entity_types=breakdown.entity_types,
            edge_types=breakdown.edge_types,
            search_questions=search_questions,
            frameworks=breakdown.frameworks,
            evidence_gathering_required=breakdown.evidence_gathering_required,
            metadata=breakdown.metadata if hasattr(breakdown, 'metadata') else {}
        )
        
    except Exception as e:
        logger.error(f"Error in breakdown: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing breakdown: {str(e)}"
        )


@router.post("/breakdown/summary", response_model=ContextBreakdownSummary)
async def breakdown_summary(request: ContextBreakdownRequest):
    """
    Get a summary of context breakdown (lightweight)
    
    Returns high-level summary with:
    - Query type and domains
    - Count of entities and search questions
    - Collections to query
    - Natural language summary
    """
    logger.info(f"Breakdown summary request: question_length={len(request.question)}")
    
    try:
        # Reuse breakdown endpoint
        full_breakdown = await breakdown(request)
        
        # Extract collections
        collections = list(set(sq.entity for sq in full_breakdown.search_questions))
        
        # Generate summary
        summary_parts = []
        summary_parts.append(f"Query type: {full_breakdown.query_type}")
        summary_parts.append(f"Domains: {', '.join(full_breakdown.domains_involved)}")
        
        if full_breakdown.product_context:
            summary_parts.append(f"Product: {full_breakdown.product_context}")
        
        if full_breakdown.frameworks:
            summary_parts.append(f"Frameworks: {', '.join(full_breakdown.frameworks)}")
        
        summary_parts.append(f"Will query {len(collections)} collections: {', '.join(collections)}")
        summary_parts.append(f"Generated {len(full_breakdown.search_questions)} search questions")
        
        if full_breakdown.evidence_gathering_required:
            summary_parts.append("Evidence gathering required")
        
        return ContextBreakdownSummary(
            session_id=full_breakdown.session_id,
            query_type=full_breakdown.query_type,
            domains_involved=full_breakdown.domains_involved,
            total_entities=len(full_breakdown.identified_entities),
            total_search_questions=len(full_breakdown.search_questions),
            collections_to_query=collections,
            summary=". ".join(summary_parts)
        )
        
    except Exception as e:
        logger.error(f"Error in breakdown summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing breakdown summary: {str(e)}"
        )
