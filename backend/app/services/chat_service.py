from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from app.models.thread import Thread, ThreadMessage, Note, Workflow
from app.schemas.thread import ThreadMessageCreate
from app.utils.logger import logger
import asyncio
import json
from datetime import datetime

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self._message_handlers = {}
        self._active_sessions = {}

    async def process_message(self, thread_id: UUID, user_id: UUID, content: str) -> Dict[str, Any]:
        """Process a chat message and return a response"""
        message = None
        timestamp = datetime.utcnow()  # Single timestamp for the entire operation
        try:
            content = {"content": content, "message_type": "text"}
            # Create message record
            message = ThreadMessage(
                id=uuid4(),
                thread_id=thread_id,
                user_id=user_id,
                content=content,
                created_at=timestamp
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            # Simulate long-running operation
            response = await self._dummy_async_service(content)
            content = {"content": response, "message_type": "text"}
            # Update message with response
            message.response = response
            message.status = "completed"
            self.db.commit()
            self.db.refresh(message)

            return {
                "message_id": str(message.id),
                "content": content,
                "response": response,
                "status": "completed",
                "timestamp": timestamp.isoformat()
            }

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            if message:
                message.status = "failed"
                message.error = str(e)
                self.db.commit()
            raise

    async def _dummy_async_service(self, content: str) -> str:
        """Simulate a long-running service"""
        await asyncio.sleep(2)  # Simulate processing time
        return f"Processed: {content}"

    def get_chat_history(self, thread_id: UUID, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history for a thread"""
        messages = self.db.query(ThreadMessage).filter(
            ThreadMessage.thread_id == thread_id
        ).order_by(ThreadMessage.created_at.desc()).limit(limit).all()

        return [{
            "message_id": str(msg.id),
            "user_id": str(msg.user_id),
            "content": msg.content,
            "response": msg.response,
            "status": msg.status,
            "timestamp": msg.created_at.isoformat()
        } for msg in reversed(messages)]

    def register_message_handler(self, message_id: UUID, handler):
        """Register a callback handler for a message"""
        self._message_handlers[str(message_id)] = handler

    def unregister_message_handler(self, message_id: UUID):
        """Unregister a callback handler"""
        self._message_handlers.pop(str(message_id), None)

    def register_session(self, session_id: str, websocket):
        """Register a new WebSocket session"""
        self._active_sessions[session_id] = websocket

    def unregister_session(self, session_id: str):
        """Unregister a WebSocket session"""
        self._active_sessions.pop(session_id, None)

    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]):
        """Send a message to a specific session"""
        if session_id in self._active_sessions:
            await self._active_sessions[session_id].send_json(message)

    async def handle_callback(self, message_id: UUID, response: Any):
        """Handle callback for async operations"""
        handler = self._message_handlers.get(str(message_id))
        if handler:
            await handler(response)
            self.unregister_message_handler(message_id) 