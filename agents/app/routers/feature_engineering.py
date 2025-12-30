from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
import json

from app.agents.nodes.transform.feature_engineering_agent import (
    generate_standard_features,
    run_feature_engineering_pipeline
)
from app.agents.pipelines.enhanced_sql_pipeline import RetrievalHelper
from app.services.transform import (
    FeatureConversationService,
    FeatureConversationRequest,
    FeatureConversationResponse
)
from app.utils.streaming import streaming_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feature-engineering", tags=["feature-engineering"])

# Service instance for conversation features (lazy initialization)
_conversation_service: Optional[FeatureConversationService] = None


def get_conversation_service() -> FeatureConversationService:
    """Get the feature conversation service instance"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = FeatureConversationService()
    return _conversation_service


class FeatureRecommendationRequest(BaseModel):
    """Request model for feature recommendations"""
    user_query: str = Field(..., description="Natural language description of analytics needs")
    project_id: str = Field(..., description="Project identifier for schema retrieval")
    domain: Optional[str] = Field(default="cybersecurity", description="Domain context (cybersecurity, hr_compliance, etc.)")
    histories: Optional[List[str]] = Field(default_factory=list, description="Previous queries for context")
    validation_expectations: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Validation examples")


class FeatureRecommendationResponse(BaseModel):
    """Response model for feature recommendations"""
    success: bool
    recommended_features: List[Dict[str, Any]] = Field(default_factory=list)
    analytical_intent: Optional[Dict[str, Any]] = None
    relevant_schemas: Optional[List[str]] = None
    clarifying_questions: Optional[List[str]] = None
    reasoning_plan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/recommend", response_model=FeatureRecommendationResponse)
async def recommend_features(request: FeatureRecommendationRequest) -> FeatureRecommendationResponse:
    """
    Generate feature recommendations based on user query.
    
    This endpoint calls the feature engineering agent to recommend KPIs and features
    that match the user's requirements.
    """
    try:
        logger.info(f"Feature recommendation request: query='{request.user_query[:100]}...', project_id={request.project_id}")
        
        # Initialize retrieval helper
        from app.agents.retrieval.retrieval_helper import RetrievalHelper
        from app.agents.nodes.transform.domain_config import get_domain_config
        
        retrieval_helper = RetrievalHelper()
        domain_config = get_domain_config(request.domain or "cybersecurity")
        
        # Use the full pipeline which properly routes through all steps
        # This ensures the workflow starts from breakdown_analysis and flows correctly
        result = await run_feature_engineering_pipeline(
            user_query=request.user_query,
            project_id=request.project_id,
            retrieval_helper=retrieval_helper,
            domain_config=domain_config,
            histories=request.histories,
            validation_expectations=request.validation_expectations
        )
        
        return FeatureRecommendationResponse(
            success=True,
            recommended_features=result.get("recommended_features", []),
            analytical_intent=result.get("analytical_intent"),
            relevant_schemas=result.get("relevant_schemas", []),
            clarifying_questions=result.get("clarifying_questions", []),
            reasoning_plan=result.get("reasoning_plan")
        )
        
    except Exception as e:
        logger.error(f"Error in feature recommendation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate feature recommendations: {str(e)}"
        )


@router.post("/full-pipeline", response_model=Dict[str, Any])
async def generate_full_pipeline(request: FeatureRecommendationRequest) -> Dict[str, Any]:
    """
    Generate full feature engineering pipeline including dependencies and transformations.
    
    This endpoint runs the complete feature engineering workflow including:
    - Feature recommendations
    - Dependency analysis
    - Transformation pipelines
    """
    try:
        logger.info(f"Full pipeline request: query='{request.user_query[:100]}...', project_id={request.project_id}")
        
        retrieval_helper = None  # TODO: Initialize if needed
        
        # Run the full pipeline
        result = await run_feature_engineering_pipeline(
            user_query=request.user_query,
            project_id=request.project_id,
            retrieval_helper=retrieval_helper,
            histories=request.histories,
            validation_expectations=request.validation_expectations
        )
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error in full pipeline generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate pipeline: {str(e)}"
        )


# ============================================================================
# CONVERSATION ENDPOINTS - Streaming and State Management
# ============================================================================

@router.post("/recommend/stream")
async def recommend_features_stream(request: FeatureConversationRequest):
    """
    Stream feature recommendations as they are generated.
    
    Returns Server-Sent Events (SSE) stream with real-time updates.
    This endpoint provides streaming feedback as features are being generated,
    allowing for better UX in chat interfaces.
    """
    try:
        service = get_conversation_service()
        request.action = "recommend"
        
        async def event_generator():
            async for update in service.process_request_with_streaming(request):
                yield f"data: {json.dumps(update)}\n\n"
                if update.get("status") in ["finished", "error"]:
                    break
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in streaming feature recommendation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream feature recommendations: {str(e)}"
        )


@router.post("/select", response_model=FeatureConversationResponse)
async def select_features(request: FeatureConversationRequest) -> FeatureConversationResponse:
    """
    Select features from recommendations and store them in cache.
    
    This endpoint:
    1. Marks features as SELECTED in the cache
    2. Adds them to the selected_features set
    3. Optionally auto-saves to file if auto_save=True
    
    The conversation context is maintained per project_id and domain combination.
    Selected features persist in cache until the conversation is cleared.
    """
    try:
        if not request.selected_feature_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_feature_ids is required for select action"
            )
        
        logger.info(f"Feature selection request: {len(request.selected_feature_ids)} features, project_id={request.project_id}, auto_save={request.auto_save}")
        
        service = get_conversation_service()
        request.action = "select"
        response = await service.process_request(request)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in feature selection: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select features: {str(e)}"
        )


@router.post("/save", response_model=FeatureConversationResponse)
async def save_features(request: FeatureConversationRequest) -> FeatureConversationResponse:
    """
    Save selected features to a file.
    
    The features are saved as JSON with metadata about the conversation including:
    - Feature definitions and pipeline structures
    - Conversation summary (queries, compliance framework, SLA requirements)
    - Timestamp and project/domain information
    
    If save_path is not provided, a default path will be generated.
    """
    try:
        logger.info(f"Save features request: project_id={request.project_id}")
        
        service = get_conversation_service()
        request.action = "save"
        
        response = await service.process_request(request)
        
        return response
        
    except Exception as e:
        logger.error(f"Error saving features: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save features: {str(e)}"
        )


@router.post("/finalize", response_model=FeatureConversationResponse)
async def finalize_workflow(request: FeatureConversationRequest) -> FeatureConversationResponse:
    """
    Finalize and version a feature workflow.
    
    This endpoint creates a finalized, versioned snapshot of the feature workflow including:
    - Workflow metadata (name, description, type, version)
    - Complete conversation history
    - All selected features with full pipeline structures
    - Complete feature registry
    
    The workflow is saved to a file with versioning. If version is not provided,
    it will be auto-generated based on existing versions.
    
    Required fields for finalization:
    - workflow_name: Name for the workflow (optional, will be auto-generated)
    - workflow_description: Description (optional, will be auto-generated)
    - workflow_type: Type of workflow (default: "feature_registry")
    - version: Version string like "1.0.0" (optional, will be auto-generated)
    """
    try:
        if not request.workflow_name:
            # Generate default name if not provided
            request.workflow_name = f"feature_workflow_{request.project_id}_{request.domain}"
        
        logger.info(f"Finalize workflow request: name={request.workflow_name}, project_id={request.project_id}")
        
        service = get_conversation_service()
        request.action = "finalize"
        
        response = await service.process_request(request)
        
        return response
        
    except Exception as e:
        logger.error(f"Error finalizing workflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize workflow: {str(e)}"
        )


@router.get("/conversation/state/{project_id}")
async def get_conversation_state(
    project_id: str,
    domain: str = "cybersecurity"
) -> Dict[str, Any]:
    """
    Get the current conversation state including all cached features.
    
    Returns information about the conversation including:
    - Total queries in the conversation
    - Total features in registry (all recommended features - cached)
    - Selected features count
    - Compliance framework (if extracted)
    - Last query
    - All cached features (complete list of all features generated so far)
    - Previous queries history
    
    Returns 404 if no active conversation is found for the project_id/domain.
    """
    try:
        service = get_conversation_service()
        state = service.get_conversation_state(project_id, domain)
        
        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active conversation found"
            )
        
        return state
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation state: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation state: {str(e)}"
        )


@router.get("/conversation/cache/{project_id}")
async def get_cached_features(
    project_id: str,
    domain: str = "cybersecurity"
) -> Dict[str, Any]:
    """
    Get all cached features for a project/domain.
    
    This endpoint returns all features that have been generated and cached
    during the conversation, regardless of whether they were selected or not.
    
    Returns empty list if no conversation exists.
    """
    try:
        service = get_conversation_service()
        cached_features = service.get_all_cached_features(project_id, domain)
        
        return {
            "project_id": project_id,
            "domain": domain,
            "total_cached": len(cached_features),
            "features": cached_features
        }
        
    except Exception as e:
        logger.error(f"Error getting cached features: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cached features: {str(e)}"
        )


@router.get("/conversation/selected/{project_id}")
async def get_selected_features(
    project_id: str,
    domain: str = "cybersecurity"
) -> Dict[str, Any]:
    """
    Get only the selected features from cache.
    
    This endpoint returns only features that have been explicitly selected
    by the user, which are stored in cache with SELECTED status.
    
    Returns empty list if no features are selected or no conversation exists.
    """
    try:
        service = get_conversation_service()
        selected_features = service.get_selected_features_from_cache(project_id, domain)
        
        return {
            "project_id": project_id,
            "domain": domain,
            "total_selected": len(selected_features),
            "features": selected_features
        }
        
    except Exception as e:
        logger.error(f"Error getting selected features: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get selected features: {str(e)}"
        )


@router.delete("/conversation/state/{project_id}")
async def clear_conversation(
    project_id: str,
    domain: str = "cybersecurity"
) -> Dict[str, str]:
    """
    Clear the conversation context.
    
    This removes all conversation history and feature registry for the project/domain.
    Use this to start a fresh conversation or reset the state.
    """
    try:
        service = get_conversation_service()
        service.clear_conversation(project_id, domain)
        
        return {
            "status": "success",
            "message": f"Conversation cleared for {project_id}/{domain}"
        }
        
    except Exception as e:
        logger.error(f"Error clearing conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear conversation: {str(e)}"
        )


@router.get("/finalized")
async def list_finalized_workflows(
    project_id: Optional[str] = None,
    domain: Optional[str] = None,
    workflow_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all finalized workflows.
    
    Returns a list of finalized workflows with their metadata.
    Can be filtered by project_id, domain, or workflow_name.
    """
    try:
        service = get_conversation_service()
        workflows = service.list_finalized_workflows(
            project_id=project_id,
            domain=domain,
            workflow_name=workflow_name
        )
        
        return {
            "total": len(workflows),
            "workflows": workflows
        }
        
    except Exception as e:
        logger.error(f"Error listing finalized workflows: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list finalized workflows: {str(e)}"
        )


@router.get("/finalized/{workflow_name}")
async def get_finalized_workflow(
    workflow_name: str,
    version: Optional[str] = None,
    project_id: Optional[str] = None,
    domain: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a specific finalized workflow by name and optionally version.
    
    If version is not provided, returns the latest version.
    """
    try:
        service = get_conversation_service()
        finalized_dir = service._save_directory / "finalized"
        
        if not finalized_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No finalized workflows found"
            )
        
        # Find the workflow file
        safe_name = workflow_name.replace(" ", "_").replace("/", "_")
        pattern = f"{safe_name}_v*.json"
        
        matching_files = []
        for file_path in finalized_dir.glob(pattern):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata = data.get("workflow_metadata", {})
                    
                    # Apply filters
                    if project_id and metadata.get("project_id") != project_id:
                        continue
                    if domain and metadata.get("domain") != domain:
                        continue
                    if metadata.get("name") != workflow_name:
                        continue
                    
                    matching_files.append((file_path, data, metadata.get("version", "1.0.0")))
            except:
                continue
        
        if not matching_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow '{workflow_name}' not found"
            )
        
        def parse_version(v_str: str) -> tuple:
            """Parse version string to tuple for comparison"""
            try:
                parts = [int(x) for x in v_str.split(".")]
                while len(parts) < 3:
                    parts.append(0)
                return tuple(parts[:3])
            except:
                return (0, 0, 0)
        
        # If version specified, find that version, otherwise get latest
        if version:
            for file_path, data, file_version in matching_files:
                if file_version == version:
                    return {
                        "workflow": data,
                        "file_path": str(file_path)
                    }
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version} of workflow '{workflow_name}' not found"
            )
        else:
            # Get latest version (highest version number)
            latest = max(matching_files, key=lambda x: parse_version(x[2]))
            return {
                "workflow": latest[1],
                "file_path": str(latest[0]),
                "version": latest[2]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting finalized workflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get finalized workflow: {str(e)}"
        )


@router.websocket("/ws/{query_id}")
async def websocket_endpoint(websocket: WebSocket, query_id: str):
    """
    WebSocket endpoint for real-time feature conversation.
    
    Supports bidirectional communication for:
    - Streaming feature recommendations
    - Feature selection
    - Save operations
    
    Message format (from client):
    {
        "action": "recommend" | "select" | "save",
        "user_query": "...",  // required for recommend
        "project_id": "...",
        "domain": "...",
        "selected_feature_ids": [...],  // required for select
        "save_path": "..."  // optional for save
    }
    
    Response format (to client):
    {
        "query_id": "...",
        "status": "processing" | "recommending" | "selecting" | "saving" | "finished" | "error",
        "recommended_features": [...],  // for recommend action
        "selected_features": [...],  // for select action
        "message": "...",
        "error": "..."  // if status is error
    }
    """
    await websocket.accept()
    await streaming_manager.register(query_id)
    
    try:
        service = get_conversation_service()
        
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Create request
            request = FeatureConversationRequest(
                query_id=query_id,
                **data
            )
            
            # Process with streaming
            async for update in service.process_request_with_streaming(request):
                await websocket.send_json(update)
                if update.get("status") in ["finished", "error"]:
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for query_id: {query_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "status": "error",
                "error": str(e)
            })
        except:
            pass
    finally:
        await streaming_manager.close(query_id)

