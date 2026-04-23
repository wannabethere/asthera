from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import logging
import asyncio
import json

from app.services.sql.ask import AskService
from app.services.sql.models import AskRequest
from app.routers.models.combined_models import CombinedAskResponse
from app.utils.streaming import streaming_manager

logger = logging.getLogger("lexy-ai-service")

router = APIRouter(prefix="/api/v1/combined", tags=["combined"])

def extract_sql_result(ask_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract SQL result and metadata from ask result."""

    print("ask_result in extract_sql_result", ask_result)
    
    # Handle AskResultResponse object (Pydantic model)
    if hasattr(ask_result, 'status') and hasattr(ask_result, 'type'):
        # This is an AskResultResponse object
        # Convert to dict to safely access all fields
        ask_result_dict = ask_result.dict() if hasattr(ask_result, 'dict') else ask_result.__dict__
        
        # Extract metadata
        metadata = ask_result_dict.get("metadata", {})
        
        # For GENERAL type responses, extract answer from metadata['data']
        answer = ask_result_dict.get("answer", "")
        if not answer and ask_result.type == "GENERAL" and metadata:
            # For GENERAL type, the data is stored in metadata['data']
            data = metadata.get("data", "")
            if isinstance(data, str):
                answer = data
            elif isinstance(data, dict):
                # If data is a dict, try to extract text content
                answer = data.get("content", data.get("text", str(data)))
        
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
            "metadata": metadata,
            "processing_time_seconds": ask_result_dict.get("processing_time_seconds", 0.0),
            "timestamp": ask_result_dict.get("timestamp", ""),
            "answer": answer,
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
    Combined endpoint that processes ask request.
    Returns response with empty question recommendations to maintain API compatibility.
    """
    try:
        # Debug logging for project_id
        logger.info(f"DEBUG: Received request with project_id: {request.project_id}")
        logger.info(f"DEBUG: project_id type: {type(request.project_id)}")
        logger.info(f"DEBUG: project_id value: {repr(request.project_id)}")
        
        # Get services from the service container
        sql_container = fastapi_request.app.state.sql_service_container
        ask_service = sql_container.get_service("ask_service")
        
        # Create AskRequest with debugging
        ask_request = AskRequest(
            query_id=request.query_id,
            query=request.query,
            project_id=request.project_id,
            project_ids=request.project_ids,
            configurations=request.configurations,
            histories=request.histories or [],
            enable_scoring=True
        )
        
        logger.info(f"DEBUG: Created AskRequest with project_id: {ask_request.project_id}")
        logger.info(f"DEBUG: AskRequest project_id type: {type(ask_request.project_id)}")
        logger.info(f"DEBUG: AskRequest project_id value: {repr(ask_request.project_id)}")
        
        # Process ask request only (question recommendations removed)
        ask_result = await ask_service.process_request(ask_request)
        
        # Extract SQL result and metadata in one go
        logger.info(f"DEBUG: ask_result before extraction: {ask_result}")
        logger.info(f"DEBUG: ask_result type: {type(ask_result)}")
        logger.info(f"DEBUG: ask_result keys: {list(ask_result.keys()) if isinstance(ask_result, dict) else (list(ask_result.dict().keys()) if hasattr(ask_result, 'dict') else 'Not a dict or Pydantic model')}")
        if hasattr(ask_result, 'metadata'):
            logger.info(f"DEBUG: ask_result.metadata: {ask_result.metadata}")
        else:
            logger.info("DEBUG: ask_result has no metadata attribute")
        sql_result = extract_sql_result(ask_result)
        logger.info(f"DEBUG: Extracted sql_result: {sql_result}")
        
        # Combine results
        try:
            # Ensure type is always a valid string, defaulting to "TEXT_TO_SQL" if None
            sql_type = sql_result.get("type") or "TEXT_TO_SQL"
            
            # Include SQL execution data in metadata
            metadata = sql_result.get("metadata", {}).copy()
            
            # Remove reasoning from metadata to avoid duplication
            # SQL generation reasoning should only be in sql_generation_reasoning field
            if "reasoning" in metadata:
                del metadata["reasoning"]
            
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
                questions={},  # Empty recommendations
                categories=[],  # Empty categories
                reasoning=None,  # Empty reasoning
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
    Streaming endpoint that processes ask request,
    providing real-time updates on the processing status.
    """
    sql_container = fastapi_request.app.state.sql_service_container
    ask_service = sql_container.get_service("ask_service")

    async def event_stream():
        ask_done = False
        # Stream ask pipeline updates
        async for ask_update in ask_service.process_request_with_streaming(request):
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
                "questions": {},  # Empty recommendations
                "categories": [],  # Empty categories
                "reasoning": None  # Empty reasoning
            }
            print(f"[DEBUG] [router] Forwarding: {combined_response}")
            yield f"data: {json.dumps(combined_response)}\n\n"
            if sql_result["status"] in ["finished", "error"]:
                ask_done = True
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    })

@router.websocket("/ws/combined")
async def websocket_combined_endpoint(websocket: WebSocket, query_id: str, fastapi_request: Request):
    """
    WebSocket endpoint that processes ask request,
    providing real-time updates on the processing status.
    """
    try:
        await websocket.accept()
        await streaming_manager.register(query_id)
        # Get services from the service container
        sql_container = fastapi_request.app.state.sql_service_container
        ask_service = sql_container.get_service("ask_service")

        try:
            # Wait for the initial request
            request_data = await websocket.receive_json()
            request = AskRequest(**request_data)
            request.query_id = query_id  # Ensure consistency between URL param and AskRequest

            ask_done = False

            # Start ask_service streaming in background
            async def process_ask_stream():
                async for update in ask_service.process_request_with_streaming(request):
                    await streaming_manager.put(query_id, update)

            ask_stream_task = asyncio.create_task(process_ask_stream())

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
                        "questions": {},  # Empty recommendations
                        "categories": [],  # Empty categories
                        "reasoning": None  # Empty reasoning
                    }
                    if sql_result["status"] in ["finished", "error"]:
                        ask_done = True

                    print(f"[DEBUG] [router] Forwarding: {combined_response}")
                    await websocket.send_json(combined_response)

                    if ask_done:
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
                await asyncio.gather(ask_stream_task, return_exceptions=True)
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