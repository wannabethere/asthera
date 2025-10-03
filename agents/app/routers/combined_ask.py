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
from app.utils.streaming import streaming_manager

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

    print("ask_result in extract_sql_result", ask_result)
    if isinstance(ask_result, str):
        return {
            "status": "finished",
            "type": "TEXT_TO_SQL",
            "response": [{"content": ask_result}],
            "error": None,
            "retrieved_tables": None,
            "sql_generation_reasoning": None,
            "is_followup": False,
            "quality_scoring": None,
            "invalid_sql": None,
            "metadata": {},
            "processing_time_seconds": 0.0,
            "timestamp": "",
            "answer": "",
            "explanation": ""
        }

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
            "invalid_sql": None,
            "metadata": {},
            "processing_time_seconds": 0.0,
            "timestamp": "",
            "answer": "",
            "explanation": ""
        }

    # Handle error case
    if not ask_result.get("success", False):
        return {
            "status": "failed",
            "type": "TEXT_TO_SQL",
            "response": None,
            "error": {
                "code": "unknown",
                "message": ask_result.get("error", "Request failed")
            },
            "retrieved_tables": None,
            "sql_generation_reasoning": None,
            "is_followup": False,
            "quality_scoring": None,
            "invalid_sql": None,
            "metadata": {},
            "processing_time_seconds": 0.0,
            "timestamp": "",
            "answer": "",
            "explanation": ""
        }

    # Extract SQL result from api_results
    api_results = ask_result.get("api_results", [])
    if api_results and isinstance(api_results, list) and len(api_results) > 0:
        sql_result = api_results[0]
        
        # Safely extract reasoning content
        metadata = ask_result.get("metadata", {})
        reasoning = metadata.get("reasoning", {})
        reasoning_content = reasoning.get("content") if isinstance(reasoning, dict) else None
        
        return {
            "status": "finished",
            "type": "TEXT_TO_SQL",
            "response": [sql_result],  # Return the entire SQL result object
            "error": None,
            "retrieved_tables": None,  # This might need to be updated if available in the response
            "sql_generation_reasoning": reasoning_content,
            "is_followup": False,
            "quality_scoring": ask_result.get("quality_scoring"),
            "invalid_sql": None,
            "metadata": metadata,
            "processing_time_seconds": ask_result.get("processing_time_seconds", 0.0),
            "timestamp": ask_result.get("timestamp", ""),
            "answer": ask_result.get("answer", ""),
            "explanation": ask_result.get("explanation", "")
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
        "invalid_sql": None,
        "metadata": {},
        "processing_time_seconds": 0.0,
        "timestamp": "",
        "answer": "",
        "explanation": ""
    }

@router.post("/combined", response_model=CombinedAskResponse)
async def process_combined_request(request: AskRequest, fastapi_request: Request):
    """
    Combined endpoint that processes both ask request and question recommendations in a single call.
    """
    try:
        # Debug logging for project_id
        logger.info(f"DEBUG: Received request with project_id: {request.project_id}")
        logger.info(f"DEBUG: project_id type: {type(request.project_id)}")
        logger.info(f"DEBUG: project_id value: {repr(request.project_id)}")
        
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
        # Create AskRequest with debugging
        ask_request = AskRequest(
            query_id=request.query_id,
            query=request.query,
            project_id=request.project_id,
            configurations=request.configurations,
            histories=request.histories or [],
            enable_scoring=True,
            schema_context={"mdl": ""}  # Add empty schema context if not provided
        )
        
        logger.info(f"DEBUG: Created AskRequest with project_id: {ask_request.project_id}")
        logger.info(f"DEBUG: AskRequest project_id type: {type(ask_request.project_id)}")
        logger.info(f"DEBUG: AskRequest project_id value: {repr(ask_request.project_id)}")
        
        ask_result, recommendation_result = await asyncio.gather(
            ask_service.process_request(ask_request),
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
            reasoning=parsed_recommendations["reasoning"],
            metadata=sql_result.get("metadata", {}),
            processing_time_seconds=sql_result.get("processing_time_seconds", 0.0),
            timestamp=sql_result.get("timestamp", ""),
            answer=sql_result.get("answer", ""),
            explanation=sql_result.get("explanation", "")
        )
        
        print(f"[DEBUG] [router] Forwarding: {combined_response}")
        
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
    sql_container = fastapi_request.app.state.sql_service_container
    ask_service = sql_container.get_service("ask_service")
    question_recommendation_service = sql_container.get_service("question_recommendation")

    # Start recommendation in parallel
    recommendation_task = asyncio.create_task(
        question_recommendation_service.recommend(QuestionRecommendation.Request(
            event_id=request.query_id,
            user_question=request.query,
            mdl="",
            project_id=request.project_id,
            configuration=request.configurations,
            previous_questions=request.previous_questions,
            max_questions=10,
            max_categories=3,
            regenerate=True
        ))
    )
    recommendation_result = None

    async def event_stream():
        nonlocal recommendation_result
        ask_done = False
        # Stream ask pipeline updates
        async for ask_update in ask_service.process_request_with_streaming(request):
            # Wait for recommendation if not done and ready
            if recommendation_result is None and recommendation_task.done():
                recommendation_result = await recommendation_task

            sql_result = extract_sql_result(ask_update)
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
                "questions": {},
                "categories": [],
                "reasoning": ""
            }
            if recommendation_result is not None:
                parsed = recommendation_result.response
                combined_response.update({
                    "questions": parsed["questions"],
                    "categories": parsed["categories"],
                    "reasoning": parsed["reasoning"]
                })
            print(f"[DEBUG] [router] Forwarding: {combined_response}")
            yield f"data: {json.dumps(combined_response)}\n\n"
            if sql_result["status"] in ["finished", "error"]:
                ask_done = True
                break
        # If ask finished but recommendation not yet, wait and send final combined
        if recommendation_result is None:
            recommendation_result = await recommendation_task
            parsed = recommendation_result.response
            combined_response.update({
                "questions": parsed["questions"],
                "categories": parsed["categories"],
                "reasoning": parsed["reasoning"]
            })
            print(f"[DEBUG] [router] Forwarding: {combined_response}")
            yield f"data: {json.dumps(combined_response)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    })

@router.websocket("/ws/combined")
async def websocket_combined_endpoint(websocket: WebSocket, query_id: str, fastapi_request: Request):
    """
    WebSocket endpoint that processes both ask request and question recommendations,
    providing real-time updates on the processing status.
    """
    try:
        await websocket.accept()
        await streaming_manager.register(query_id)
        # Get services from the service container
        sql_container = fastapi_request.app.state.sql_service_container
        ask_service = sql_container.get_service("ask_service")
        question_recommendation_service = sql_container.get_service("question_recommendation")

        try:
            # Wait for the initial request
            request_data = await websocket.receive_json()
            request = AskRequest(**request_data)
            request.query_id = query_id  # Ensure consistency between URL param and AskRequest

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

            ask_done = False
            recommendation_done = False
            recommendation_result = None
            parsed_recommendations = None

            # Start ask_service streaming in background
            async def process_ask_stream():
                async for update in ask_service.process_request_with_streaming(request):
                    await streaming_manager.put(query_id, update)

            ask_stream_task = asyncio.create_task(process_ask_stream())
            recommendation_task = asyncio.create_task(
                question_recommendation_service.recommend(recommendation_request)
            )

            try:
                # Stream ask results from the manager
                while True:
                    ask_update = await streaming_manager.get(query_id)
                    if not isinstance(ask_update, dict):
                        ask_update = {"status": "unknown", "data": ask_update}
                    if ask_update.get("status") == "starting":
                        continue
                    sql_result = extract_sql_result(ask_update)
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
                        "questions": {},
                        "categories": [],
                        "reasoning": ""
                    }
                    if sql_result["status"] in ["finished", "error"]:
                        ask_done = True
                        if not recommendation_done:
                            recommendation_result = await recommendation_task
                            parsed_recommendations = recommendation_result.response
                            combined_response.update({
                                "questions": parsed_recommendations["questions"],
                                "categories": parsed_recommendations["categories"],
                                "reasoning": parsed_recommendations["reasoning"]
                            })
                            recommendation_done = True
                    if not recommendation_done and recommendation_task.done():
                        recommendation_result = await recommendation_task
                        parsed_recommendations = recommendation_result.response
                        combined_response.update({
                            "questions": parsed_recommendations["questions"],
                            "categories": parsed_recommendations["categories"],
                            "reasoning": parsed_recommendations["reasoning"]
                        })
                        recommendation_done = True

                    print(f"[DEBUG] [router] Forwarding: {combined_response}")
                    await websocket.send_json(combined_response)

                    if ask_done and recommendation_done:
                        await streaming_manager.close(query_id)
                        break
            except Exception as e:
                error_response = {
                    "status": "error",
                    "error": {
                        "code": "WEBSOCKET_ERROR",
                        "message": str(e)
                    }
                }
                await websocket.send_json(error_response)
                await streaming_manager.close(query_id)
            finally:
                await asyncio.gather(ask_stream_task, recommendation_task, return_exceptions=True)
        except WebSocketDisconnect:
            await streaming_manager.close(query_id)
        except Exception as e:
            error_response = {
                "status": "error",
                "error": {
                    "code": "WEBSOCKET_ERROR",
                    "message": str(e)
                }
            }
            await websocket.send_json(error_response)
            await streaming_manager.close(query_id)
        finally:
            await streaming_manager.close(query_id)
    except Exception as e:
        if websocket.client_state.CONNECTED:
            await websocket.close(code=1011, reason=str(e)) 
        await streaming_manager.close(query_id) 