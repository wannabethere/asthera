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
    
    # Handle AskResultResponse object (Pydantic model)
    if hasattr(ask_result, 'status') and hasattr(ask_result, 'type'):
        # This is an AskResultResponse object
        # Convert to dict to safely access all fields
        ask_result_dict = ask_result.dict() if hasattr(ask_result, 'dict') else ask_result.__dict__
        
        return {
            "status": ask_result.status,
            "type": ask_result.type or "TEXT_TO_SQL",  # Ensure type is never None
            "response": ask_result.response,
            "error": ask_result.error,
            "retrieved_tables": ask_result.retrieved_tables,
            "sql_generation_reasoning": ask_result.sql_generation_reasoning,
            "is_followup": getattr(ask_result, 'is_followup', False),
            "quality_scoring": ask_result.quality_scoring,
            "invalid_sql": getattr(ask_result, 'invalid_sql', None),
            "metadata": ask_result_dict.get("metadata", {}),
            "processing_time_seconds": ask_result_dict.get("processing_time_seconds", 0.0),
            "timestamp": ask_result_dict.get("timestamp", ""),
            "answer": ask_result_dict.get("answer", ""),
            "explanation": ask_result_dict.get("explanation", "")
        }
    
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

    # Handle successful result from ask service
    if ask_result.get("success", False) and "api_results" in ask_result:
        # Extract the successful result
        api_results = ask_result.get("api_results", [])
        metadata = ask_result.get("metadata", {})
        
        return {
            "status": "finished",
            "type": "TEXT_TO_SQL",
            "response": api_results,
            "error": None,
            "retrieved_tables": None,
            "sql_generation_reasoning": metadata.get("reasoning"),
            "is_followup": False,
            "quality_scoring": ask_result.get("quality_scoring"),
            "invalid_sql": None,
            "metadata": metadata,
            "processing_time_seconds": metadata.get("processing_time_seconds", 0.0),
            "timestamp": metadata.get("timestamp", ""),
            "answer": ask_result.get("answer", metadata.get("answer", "")),
            "explanation": ask_result.get("explanation", metadata.get("explanation", ""))
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
            enable_scoring=True
        )
        
        logger.info(f"DEBUG: Created AskRequest with project_id: {ask_request.project_id}")
        logger.info(f"DEBUG: AskRequest project_id type: {type(ask_request.project_id)}")
        logger.info(f"DEBUG: AskRequest project_id value: {repr(ask_request.project_id)}")
        
        ask_result, recommendation_result = await asyncio.gather(
            ask_service.process_request(ask_request),
            question_recommendation_service.recommend(recommendation_request)
        )
        
        # Extract SQL result and metadata in one go
        logger.info(f"DEBUG: ask_result before extraction: {ask_result}")
        logger.info(f"DEBUG: ask_result type: {type(ask_result)}")
        logger.info(f"DEBUG: ask_result keys: {list(ask_result.keys()) if isinstance(ask_result, dict) else 'Not a dict'}")
        if hasattr(ask_result, 'metadata'):
            logger.info(f"DEBUG: ask_result.metadata: {ask_result.metadata}")
        else:
            logger.info("DEBUG: ask_result has no metadata attribute")
        sql_result = extract_sql_result(ask_result)
        logger.info(f"DEBUG: Extracted sql_result: {sql_result}")
        
        # Parse recommendation content
        parsed_recommendations = recommendation_result.response
        logger.info(f"DEBUG: Parsed recommendations: {parsed_recommendations}")
        
        # Combine results
        try:
            # Ensure type is always a valid string, defaulting to "TEXT_TO_SQL" if None
            sql_type = sql_result.get("type") or "TEXT_TO_SQL"
            
            # Include SQL execution data in metadata
            metadata = sql_result.get("metadata", {})
            
            # The SQL execution data should be available in the ask_result
            if hasattr(ask_result, 'metadata') and ask_result.metadata:
                logger.info(f"DEBUG: ask_result.metadata: {ask_result.metadata}")
                # Look for sql_data first (stored by ask service), then sql_execution_data as fallback
                sql_execution_data = ask_result.metadata.get('sql_data') or ask_result.metadata.get('sql_execution_data')
                logger.info(f"DEBUG: sql_execution_data found: {sql_execution_data}")
                if sql_execution_data:
                    metadata["sql_execution_data"] = sql_execution_data
                else:
                    # Fallback if no execution data found
                    metadata["sql_execution_data"] = {
                        "success": True,
                        "data": [],
                        "columns": [],
                        "row_count": 0,
                        "message": "SQL executed successfully but returned no results"
                    }
            else:
                # Fallback if no metadata found
                metadata["sql_execution_data"] = {
                    "success": True,
                    "data": [],
                    "columns": [],
                    "row_count": 0,
                    "message": "SQL executed successfully but returned no results"
                }
            
            combined_response = CombinedAskResponse(
                status=sql_result["status"],
                type=sql_type,
                response=sql_result["response"],
                error=sql_result["error"],
                retrieved_tables=sql_result["retrieved_tables"],
                sql_generation_reasoning=sql_result["sql_generation_reasoning"],
                is_followup=sql_result["is_followup"],
                quality_scoring=sql_result["quality_scoring"],
                invalid_sql=sql_result["invalid_sql"],
                questions=parsed_recommendations["questions"],
                categories=parsed_recommendations["categories"],
                reasoning=sql_result.get("sql_generation_reasoning", ""),
                metadata=metadata,
                processing_time_seconds=sql_result.get("processing_time_seconds", 0.0),
                timestamp=sql_result.get("timestamp", ""),
                answer=sql_result.get("answer") or "",
                explanation=sql_result.get("explanation") or ""
            )

            print(f"[DEBUG] [router] CombinedAskResponse: {combined_response}")
        except Exception as e:
            logger.error(f"Error creating CombinedAskResponse: {e}")
            logger.error(f"sql_result keys: {list(sql_result.keys())}")
            logger.error(f"sql_result values: {sql_result}")
            raise
        
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
            # Ensure type is always a valid string, defaulting to "TEXT_TO_SQL" if None
            sql_type = sql_result.get("type") or "TEXT_TO_SQL"
            
            combined_response = {
                "status": sql_result["status"],
                "type": sql_type,
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
                    # Ensure type is always a valid string, defaulting to "TEXT_TO_SQL" if None
                    sql_type = sql_result.get("type") or "TEXT_TO_SQL"
                    
                    combined_response = {
                        "status": sql_result["status"],
                        "type": sql_type,
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