from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.thread import Thread, ThreadMessage
from app.models.user import User
from app.auth.okta import get_current_user, get_current_user_ws
from app.schemas.chat import MessageCreate, MessageResponse, ChatHistoryResponse
from app.services.authorization import check_project_access
from typing import List
from uuid import UUID, uuid4
from app.services.chat_service import ChatService
from app.utils.logger import logger
import json

router = APIRouter(prefix="/chat", tags=["chat"])

# Store active chat services
chat_services = {}

@router.post("/message", response_model=MessageResponse)
async def add_message(
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a new message to a thread.
    Requires JWT authentication and project access.
    """
    try:
        # Get the thread
        thread = db.query(Thread).filter(Thread.id == message_data.thread_id).first()
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )

        # Check if user has access to the project
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to post messages in this thread"
            )

        # Create new message
        message = ThreadMessage(
            thread_id=message_data.thread_id,
            user_id=current_user.id,
            content=message_data.message
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return message
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding message: {str(e)}"
        )

@router.get("/history/{thread_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get chat history for a specific thread.
    Messages are returned in chronological order.
    Requires JWT authentication and project access.
    """
    try:
        # Get the thread
        thread = db.query(Thread).filter(Thread.id == thread_id).first()
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )

        # Check if user has access to the project
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view messages in this thread"
            )

        # Get messages in chronological order
        messages = db.query(ThreadMessage)\
            .filter(ThreadMessage.thread_id == thread_id)\
            .order_by(ThreadMessage.created_at.asc())\
            .all()

        return ChatHistoryResponse(
            thread_id=thread_id,
            messages=messages
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chat history: {str(e)}"
        )

@router.put("/message/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: UUID,
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing message in a thread.
    Only the original message creator can update their message.
    Requires JWT authentication and project access.
    """
    try:
        # Get the message
        message = db.query(ThreadMessage).filter(ThreadMessage.id == message_id).first()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        # Check if user is the message creator
        if message.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this message"
            )

        # Get the thread to check project access
        thread = db.query(Thread).filter(Thread.id == message.thread_id).first()
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )

        # Check if user has access to the project
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update messages in this thread"
            )

        # Update message content
        message.content = message_data.message
        db.commit()
        db.refresh(message)
        
        return message
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating message: {str(e)}"
        )

@router.websocket("/ws/{thread_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    thread_id: UUID
):
    try:
        # Get database session
        db = next(get_db())
        
        # Get JWT token from query parameters or headers
        token = None
        if "token" in websocket.query_params:
            token = websocket.query_params["token"]
        else:
            # Try to get token from headers
            auth_header = websocket.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            await websocket.close(code=4001, reason="No authentication token provided")
            return

        # Verify token and get user
        try:
            current_user = await get_current_user_ws(token, db)
            if not current_user:
                await websocket.close(code=4001, reason="Invalid authentication token")
                return
            logger.info(f"Authenticated user: {current_user.id}")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            await websocket.close(code=4001, reason="Authentication failed")
            return

        # Accept the connection after authentication
        await websocket.accept()
        
        # Check if thread exists
        thread = db.query(Thread).filter(Thread.id == thread_id).first()
        if not thread:
            logger.error(f"Thread not found: {thread_id}")
            await websocket.close(code=4004, reason="Thread not found")
            return
            
        logger.info(f"Found thread: {thread_id}, project_id: {thread.project_id}")
        
        #Dont check access for project here, we will do that before the thread is created outside scope of this function
            
        logger.info(f"Access granted for user {current_user.id} to thread {thread_id}")

        # Get or create chat service for this thread
        if thread_id not in chat_services:
            chat_services[thread_id] = ChatService(db)
        
        chat_service = chat_services[thread_id]
        session_id = f"{thread_id}_{current_user.id}"
        
        # Register session
        chat_service.register_session(session_id, websocket)
        logger.info(f"Registered session: {session_id}")
        
        # Send chat history
        history = chat_service.get_chat_history(thread_id)
        await websocket.send_json({
            "type": "history",
            "data": history
        })
        logger.info(f"Sent chat history for thread {thread_id}")

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                
                if data["type"] == "message":
                    content = data["content"]
                    message_id = UUID(data.get("message_id", str(uuid4())))
                    logger.info(f"Received message: {content}")
                    # Process message asynchronously
                    async def handle_response(response):
                        try:
                            await chat_service.broadcast_to_session(session_id, {
                                "type": "response",
                                "data": response
                            })
                        except Exception as e:
                            logger.error(f"Error in handle_response: {str(e)}")
                    
                    # Register callback handler
                    chat_service.register_message_handler(message_id, handle_response)
                    
                    # Process message
                    response = await chat_service.process_message(
                        thread_id=thread_id,
                        user_id=current_user.id,
                        content=content
                    )
                    
                    # Send immediate acknowledgment
                    await websocket.send_json({
                        "type": "ack",
                        "data": {
                            "message_id": str(message_id),
                            "status": "processing"
                        }
                    })
                    
                    # Handle response through callback
                    await chat_service.handle_callback(message_id, response)
                
                elif data["type"] == "ping":
                    await websocket.send_json({"type": "pong"})

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {session_id}")
            chat_service.unregister_session(session_id)
            
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.close(code=4000, reason=str(e))
    finally:
        db.close() 