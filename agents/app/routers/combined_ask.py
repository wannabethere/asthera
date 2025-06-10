from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator
import re
import logging
import asyncio
import json

from app.services.sql.ask import AskService
from app.services.sql.question_recommendation import QuestionRecommendation
from app.services.sql.models import AskRequest
from app.routers.models.combined_models import CombinedAskResponse
from app.agents.nodes.sql.utils.sql_prompts import Configuration as SQLConfiguration

logger = logging.getLogger("lexy-ai-service")

router = APIRouter(prefix="/api/v1/combined", tags=["combined"])

def parse_recommendation_content(content: str) -> Dict[str, Any]:
    """Parse the recommendation content into structured format."""
    questions = {}
    categories = []
    current_category = None
    reasoning = ""
    
    # Split content into lines and process
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for category headers
        if line.startswith('### Category'):
            current_category = line.replace('### Category', '').strip(': ')
            categories.append(current_category)
            questions[current_category] = []
        # Check for numbered questions
        elif line[0].isdigit() and '. ' in line:
            if current_category:
                question = line.split('. ', 1)[1]
                questions[current_category].append(question)
        # Add any non-category, non-question lines to reasoning
        elif not line.startswith('###') and not line[0].isdigit():
            reasoning += line + "\n"
    
    return {
        "questions": questions,
        "categories": categories,
        "reasoning": reasoning.strip()  # Return as string instead of list
    }

def extract_sql_result(ask_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract SQL result and metadata from ask result."""
    if not isinstance(ask_result, dict):
        return {
            "status": "unknown",
            "type": "TEXT_TO_SQL",
            "response": None,
            "error": None,
            "retrieved_tables": None,
            "sql_generation_reasoning": None,
            "is_followup": False,
            "quality_scoring": None,
            "invalid_sql": None
        }

    # Handle error case
    if not ask_result.get("success", False):
        return {
            "status": "failed",
            "type": "TEXT_TO_SQL",
            "response": None,
            "error": {
                "code": "unknown",
                "message": "Request failed"
            },
            "retrieved_tables": None,
            "sql_generation_reasoning": None,
            "is_followup": False,
            "quality_scoring": None,
            "invalid_sql": None
        }

    # Extract SQL result from api_results
    api_results = ask_result.get("api_results", [])
    if api_results and isinstance(api_results, list) and len(api_results) > 0:
        sql_result = api_results[0]
        return {
            "status": "finished",
            "type": "TEXT_TO_SQL",
            "response": [sql_result],  # Return the entire SQL result object
            "error": None,
            "retrieved_tables": None,  # This might need to be updated if available in the response
            "sql_generation_reasoning": ask_result.get("metadata", {}).get("reasoning", {}).get("content"),
            "is_followup": False,
            "quality_scoring": ask_result.get("quality_scoring"),
            "invalid_sql": None
        }

    return {
        "status": "unknown",
        "type": "TEXT_TO_SQL",
        "response": None,
        "error": None,
        "retrieved_tables": None,
        "sql_generation_reasoning": None,
        "is_followup": False,
        "quality_scoring": None,
        "invalid_sql": None
    }

@router.post("/combined", response_model=CombinedAskResponse)
async def process_combined_request(request: AskRequest, fastapi_request: Request):
    """
    Combined endpoint that processes both ask request and question recommendations in a single call.
    """
    try:
        # Get services from the service container
        sql_container = fastapi_request.app.state.sql_service_container
        ask_service = sql_container.get_service("ask_service")
        question_recommendation_service = sql_container.get_service("question_recommendation")
        
        # Create recommendation request upfront
        recommendation_request = QuestionRecommendation.Request(
            event_id=request.query_id,
            user_question=request.query,
            mdl="",
            project_id=request.project_id,
            configuration=request.configurations,
            previous_questions=request.previous_questions,
            max_questions=10,
            max_categories=3,
            regenerate=True
        )
        
        # Process ask request and recommendations in parallel
        ask_result, recommendation_result = await asyncio.gather(
            ask_service.process_request(request),
            question_recommendation_service.recommend(recommendation_request)
        )
        
        # Extract SQL result and metadata in one go
        sql_result = extract_sql_result(ask_result)
        
        # Parse recommendation content
        parsed_recommendations = recommendation_result.response
        
        # Combine results
        combined_response = CombinedAskResponse(
            status=sql_result["status"],
            type=sql_result["type"],
            response=sql_result["response"],
            error=sql_result["error"],
            retrieved_tables=sql_result["retrieved_tables"],
            sql_generation_reasoning=sql_result["sql_generation_reasoning"],
            is_followup=sql_result["is_followup"],
            quality_scoring=sql_result["quality_scoring"],
            invalid_sql=sql_result["invalid_sql"],
            questions=parsed_recommendations["questions"],
            categories=parsed_recommendations["categories"],
            reasoning=parsed_recommendations["reasoning"]
        )
        
        return combined_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing combined request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing combined request: {str(e)}"
        )

@router.post("/combined/stream")
async def process_combined_request_stream(request: AskRequest, fastapi_request: Request):
    """
    Streaming endpoint that processes both ask request and question recommendations,
    providing real-time updates on the processing status.
    """
    try:
        # Get services from the service container
        sql_container = fastapi_request.app.state.sql_service_container
        ask_service = sql_container.get_service("ask_service")
        question_recommendation_service = sql_container.get_service("question_recommendation")

        async def generate_stream():
            try:
                # Create recommendation request upfront
                recommendation_request = QuestionRecommendation.Request(
                    event_id=request.query_id,
                    user_question=request.query,
                    mdl="",
                    project_id=request.project_id,
                    configuration=request.configurations,
                    previous_questions=request.previous_questions,
                    max_questions=10,
                    max_categories=3,
                    regenerate=True
                )

                # Process ask request with streaming and recommendations in parallel
                ask_stream = ask_service.process_request_with_streaming(request)
                recommendation_task = asyncio.create_task(
                    question_recommendation_service.recommend(recommendation_request)
                )

                # Stream ask results
                async for ask_update in ask_stream:
                    # Extract SQL result and metadata
                    sql_result = extract_sql_result(ask_update)
                    
                    # Create combined response
                    combined_response = {
                        "status": sql_result["status"],
                        "type": sql_result["type"],
                        "response": sql_result["response"],
                        "error": sql_result["error"],
                        "retrieved_tables": sql_result["retrieved_tables"],
                        "sql_generation_reasoning": sql_result["sql_generation_reasoning"],
                        "is_followup": sql_result["is_followup"],
                        "quality_scoring": sql_result["quality_scoring"],
                        "invalid_sql": sql_result["invalid_sql"],
                        "questions": {},  # Will be updated when recommendations are ready
                        "categories": [],
                        "reasoning": ""
                    }

                    # If this is the final update, include recommendations
                    if sql_result["status"] in ["finished", "error"]:
                        recommendation_result = await recommendation_task
                        parsed_recommendations = recommendation_result.response
                        combined_response.update({
                            "questions": parsed_recommendations["questions"],
                            "categories": parsed_recommendations["categories"],
                            "reasoning": parsed_recommendations["reasoning"]
                        })

                    yield f"data: {json.dumps(combined_response)}\n\n"

            except Exception as e:
                error_response = {
                    "status": "error",
                    "error": {
                        "code": "STREAMING_ERROR",
                        "message": str(e)
                    }
                }
                yield f"data: {json.dumps(error_response)}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"Error setting up streaming response: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error setting up streaming response: {str(e)}"
        )

@router.websocket("/ws/combined")
async def websocket_combined_endpoint(websocket: WebSocket, query_id: str, fastapi_request: Request):
    """
    WebSocket endpoint that processes both ask request and question recommendations,
    providing real-time updates on the processing status.
    """
    try:
        await websocket.accept()
        
        # Get services from the service container
        sql_container = fastapi_request.app.state.sql_service_container
        ask_service = sql_container.get_service("ask_service")
        question_recommendation_service = sql_container.get_service("question_recommendation")

        try:
            # Wait for the initial request
            request_data = await websocket.receive_json()
            request = AskRequest(**request_data)

            # Create recommendation request
            recommendation_request = QuestionRecommendation.Request(
                event_id=request.query_id,
                user_question=request.query,
                mdl="",
                project_id=request.project_id,
                configuration=request.configurations,
                previous_questions=request.previous_questions,
                max_questions=10,
                max_categories=3,
                regenerate=True
            )

            # Process ask request with streaming and recommendations in parallel
            ask_stream = ask_service.process_request_with_streaming(request)
            recommendation_task = asyncio.create_task(
                question_recommendation_service.recommend(recommendation_request)
            )

            # Stream ask results
            async for ask_update in ask_stream:
                # Extract SQL result and metadata
                sql_result = extract_sql_result(ask_update)
                
                # Create combined response
                combined_response = {
                    "status": sql_result["status"],
                    "type": sql_result["type"],
                    "response": sql_result["response"],
                    "error": sql_result["error"],
                    "retrieved_tables": sql_result["retrieved_tables"],
                    "sql_generation_reasoning": sql_result["sql_generation_reasoning"],
                    "is_followup": sql_result["is_followup"],
                    "quality_scoring": sql_result["quality_scoring"],
                    "invalid_sql": sql_result["invalid_sql"],
                    "questions": {},  # Will be updated when recommendations are ready
                    "categories": [],
                    "reasoning": ""
                }

                # If this is the final update, include recommendations
                if sql_result["status"] in ["finished", "error"]:
                    recommendation_result = await recommendation_task
                    parsed_recommendations = recommendation_result.response
                    combined_response.update({
                        "questions": parsed_recommendations["questions"],
                        "categories": parsed_recommendations["categories"],
                        "reasoning": parsed_recommendations["reasoning"]
                    })

                await websocket.send_json(combined_response)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for query_id: {query_id}")
        except Exception as e:
            logger.error(f"Error in WebSocket processing: {str(e)}", exc_info=True)
            error_response = {
                "status": "error",
                "error": {
                    "code": "WEBSOCKET_ERROR",
                    "message": str(e)
                }
            }
            await websocket.send_json(error_response)
        finally:
            # Clean up streaming connections
            ask_service.stop_streaming(query_id)

    except Exception as e:
        logger.error(f"Error in WebSocket setup: {str(e)}", exc_info=True)
        if websocket.client_state.CONNECTED:
            await websocket.close(code=1011, reason=str(e)) 