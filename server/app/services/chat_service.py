from typing import Dict, List, Optional, Any
import requests
import aiohttp
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from app.models.thread import Thread, ThreadMessage, Note, Workflow
from app.schemas.thread import ThreadMessageCreate, TraceCreate
from app.utils.logger import logger
import asyncio
import json
import time  # Added missing import
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from enum import Enum
import traceback
import os
from sqlalchemy.orm.attributes import flag_modified
from app.services.audit_service import AuditService

class QueryType(Enum):
    SQL = "sql"
    FOLLOWUP = "followup"
    RECOMMENDED_QUESTIONS = "recommended-questions"
    ADJUST_VISUAL = "adjust-visual"
    EXPAND = "expand"
    UNSTRUCTURED = "unstructured"

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.base_url = os.getenv("CHAT_API_BASE_URL", "http://ec2-18-204-196-65.compute-1.amazonaws.com:8025")
        self.doc_url = os.getenv("doc_url","http://ec2-18-204-196-65.compute-1.amazonaws.com:8080")
        self.project_id = None
        self.timeout = int(os.getenv("API_TIMEOUT", "600"))
        self.headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": f"{self.base_url}/",
            "Referer": f"{self.base_url}/",
            "Content-Type": "application/json"
        }
        self.doc_headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": f"{self.doc_url}/",
            "Referer": f"{self.doc_url}/",
            "Content-Type": "application/json"
        }
        self._message_handlers = {}
        self._active_sessions = {}
        self.audit_service = AuditService(db)
        self.audit_id = None

    def _validate_content(self, content: Dict, required_fields: List[str]) -> bool:
        """Validate that required fields are present in content"""
        if not isinstance(content, dict):
            return False
        
            
        return all(field in content['content'] for field in required_fields)
    
    async def process_message(self, thread_id: UUID, user_id: UUID, content: Dict, doc_id: List[str]) -> Dict[str, Any]:
        """Process a chat message and return a response"""
        timestamp = datetime.utcnow()
        logger.info(f"Content I got in process message is {content}")
        
        try:
            message_content = {"content": content, "message_type": "text"}
            # Validate basic content structure
            if not self._validate_content(message_content, ['question_type']):
                return {
                    "content": {"content": content, "message_type": "text"},
                    "response": {"error": "Invalid content structure. 'question_type' is required."},
                    "status": "failed",
                    "timestamp": timestamp.isoformat()
                }

            logger.info("Processing message content")
            msgid = content.get('message_id')
            logger.info(f"This is the msg Id {msgid}")
            message = None
            
            if msgid:
                message = self.db.query(ThreadMessage).filter(
                    ThreadMessage.thread_id == thread_id,
                    ThreadMessage.id == msgid
                ).first()
            
            try:
                if not message:
                    # Step 1: Create new message with empty response first
                    logger.info("create a record")
                    new_message = ThreadMessage(
                        id=uuid4(),
                        thread_id=thread_id,
                        user_id=user_id,
                        content=content,
                        response={},  # Empty response initially
                        status="Processing",  # Changed from "Completed"
                        created_at=timestamp
                    )
                    self.db.add(new_message)
                    self.db.flush()  # This ensures the message gets an ID
                    
                    # Step 2: Create audit now that message exists
                    new_audit = await self.audit_service.create_audit(
                        message_content['content'].get('question', '').strip(),
                        {
                            "user_id": user_id,
                            "message_id": new_message.id,  # Now we have the message ID
                        }
                    )
                    self.audit_id = new_audit.auditid
                    logger.info(f"Created audit {new_audit} {self.audit_id}")
                    
                    # Step 3: Now handle the message (this will create traces)
                    response = await self.handle_message(message_content, thread_id, user_id, doc_id)
                    
                    # Step 4: Update message with actual response
                    new_message.response = response
                    new_message.status = "Completed"
                    self.db.add(new_message)
                    
                    return_response = {
                        "message_id": str(new_message.id),
                        "content": message_content,
                        "response": response,
                        "status": "completed",
                        "timestamp": timestamp.isoformat()
                    }
                    
                    try:
                        logger.info("In Try Block")
                        self.db.commit()
                        logger.info(f"After Try lock commit {return_response}")
                        return return_response
                    except Exception as e:
                        logger.info(f"Error in commit please see {traceback.print_exc()}")
                        return return_response
                else:
                    logger.info("Updating record")
                    # For existing messages, handle normally
                    response = await self.handle_message(message_content, thread_id, user_id, doc_id)
                    
                    # Update existing message
                    message.response = response
                    flag_modified(message, "response")
                    self.db.commit()
                    
                    return {
                        "message_id": str(message.id),
                        "content": message_content,
                        "response": response,
                        "status": "completed",
                        "timestamp": timestamp.isoformat()
                    }
                    
            except SQLAlchemyError as db_error:
                self.db.rollback()
                logger.exception(f"Database error: {db_error}")
                return {
                    "content": {"content": content, "message_type": "text"},
                    "response": {"error": "Database operation failed"},
                    "status": "failed",
                    "timestamp": timestamp.isoformat()
                }

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error processing message: {e}\nTraceback: {error_traceback}")
            
            # Rollback any pending database changes
            try:
                self.db.rollback()
            except:
                pass
                
            return {
                "content": {"content": content, "message_type": "text"},
                "response": {
                    "error": str(e),
                    "traceback": error_traceback
                },
                "status": "failed",
                "timestamp": timestamp.isoformat()
            }
    
    
    async def handle_message(self, content: Dict, thread_id: UUID, user_id: UUID, doc_id: List[str]) -> Dict[str, Any]:
        """Handle different types of messages"""
        logger.info("Entered into handle message...")
        try:
            query_type = content['content'].get('question_type', '').lower()
            msgid = content['content'].get('message_id')
            
            logger.info(f"Handling message type: {query_type}")
            
            # For operations that need existing message
            message = None
            if msgid:
                message = self.db.query(ThreadMessage).filter(
                    ThreadMessage.thread_id == thread_id,
                    ThreadMessage.id == msgid
                ).first()
                
                if not message:
                    raise ValueError("Message not found. Please send the message again")
            
            # Route to appropriate handler
            if query_type == QueryType.SQL.value and not msgid:
                logger.info("Entered SQL Agent...")
                if not self._validate_content(content, ['question']):
                    logger.info("Entered not validate condition if loop...")
                    return {"error": "Invalid content: 'question' field is required for SQL queries."}
                logger.info("Crossed validate function loop")
                response = await self._handle_sql_query(content, thread_id, user_id, doc_id)
                result = {}
                result["OriginalResponse"] = {"SQLResponse": response}
                result["CurrentResponse"] = {"SQLResponse": response}
                return result
                
            elif query_type == QueryType.FOLLOWUP.value and msgid:
                if not self._validate_content(content, ['question', 'sqlquery']):
                    return {"error": "Invalid content: 'question' and 'sqlquery' fields are required for followup queries."}
                
                followup_response = await self._handle_followup_query(content, thread_id, user_id, doc_id, message)
                rec_questions_response = await self._handle_recommended_questions(content, thread_id, user_id, doc_id, message)
                
                if message and message.response:
                    message.response["OriginalResponse"]["FollowupResponse"] = followup_response
                    message.response["CurrentResponse"]["FollowupResponse"] = followup_response
                    message.response["OriginalResponse"]["RecommendedQuestions"] = rec_questions_response
                    message.response["CurrentResponse"]["RecommendedQuestions"] = rec_questions_response
                return message.response
                
            elif query_type == QueryType.ADJUST_VISUAL.value and msgid:
                if not self._validate_content(content, ['question', 'sql', 'adjustments']):
                    return {"error": "Invalid content: 'question', 'sql', and 'adjustments' fields are required for visual adjustments."}
                    
                response = await self._handle_adjust_visual(content, thread_id, user_id, doc_id, message)
                if message and message.response:
                    message.response["CurrentResponse"]["CurrentAdjustments"] = response
                return message.response
                
            elif query_type == QueryType.EXPAND.value and msgid:
                if not self._validate_content(content, ['question']):
                    return {"error": "Invalid content: 'question' field is required for expand queries."}
                    
                return await self._handle_expand_query(content, thread_id, user_id, doc_id, message)

            elif query_type == QueryType.UNSTRUCTURED.value and not msgid:
                logger.info("Entered in unstructured")
                if not self._validate_content(content, ['question']):
                        return {"error": "Invalid content: 'question' field is required for expand queries."}
                logger.info("going t0 _handle_unstructered_query")
                return await self._handle_unstructered_query(content, thread_id, user_id, doc_id, message)
            else:
                return {"error": f"Unsupported query type: {query_type}"}

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error in handle_message: {e}\nTraceback: {error_traceback}")
            return {
                "error": "Internal server error",
                "details": str(e),
                "traceback": error_traceback
            }

    async def _handle_sql_query(self, content: Dict, thread_id: UUID, user_id: UUID, doc_id: List[str]) -> Dict[str, Any]:
        """Handle SQL query requests"""
        start_time = time.time()
        trace_id = None
        try:
            msg = content['content'].get('question', '').strip()
            self.project_id = content['content'].get('project_id', 'cornerstone').strip()
            if not msg:
                return {"error": "Invalid content: 'question' field is required and cannot be empty."}

            # Create trace for SQL Agent
            if self.audit_id:
                trace_data = TraceCreate(
                    auditid=self.audit_id,
                    sequence=1,
                    component="SQL Agent",
                    status="running",
                    input_data={"question": content['content'].get('question', '').strip()},
                    output_data=None,
                    time_taken=None
                )
                trace_response = await self.audit_service.create_trace(trace_data)
                trace_id = trace_response.trace_id

            url = f"{self.base_url}/api/v1/combined/combined"
            data = {
                "query": msg,
                "project_id": self.project_id,
                "mdl_hash": "string",
                "thread_id": str(thread_id),
                "histories": [{"sql": "string", "question": "string"}],
                "configurations": {
                    "language": "English",
                    "timezone": {"name": "UTC", "utc_offset": ""}
                },
                "enable_scoring": True,
                "previous_questions": ["string"]
            }

            response = await self._make_api_request(url, data, "SQL")
            
            # Add additional fields
            response.update({
                "asked_question": msg,
                "project_id": data["project_id"]
            })
            
            # Update trace as completed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "completed", 
                    response, 
                    end_time - start_time
                )
            
            return response

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error in _handle_sql_query: {e}\nTraceback: {error_traceback}")
            
            # Update trace as failed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "failed", 
                    {"error": str(e), "traceback": error_traceback}, 
                    end_time - start_time
                )
            
            return {
                "error": "SQL query failed",
                "details": str(e),
                "traceback": error_traceback
            }

    async def _handle_followup_query(self, content: Dict, thread_id: UUID, user_id: UUID, doc_id: List[str], message: ThreadMessage) -> Dict[str, Any]:
        """Handle followup query requests"""
        start_time = time.time()
        trace_id = None
        try:
            msg = content['content'].get('question', '').strip()
            print(f"{self.project_id} in Follow up")
            sql_query = content['content'].get('sqlquery', '')
            if isinstance(sql_query, list):
                sql_query=sql_query[0]
            
            if not msg or not sql_query:
                return {"error": "Both 'question' and 'sqlquery' fields are required for followup queries."}
            
            logger.info("Processing followup query")
            
            # Create trace for Visual Generation Agent
            if self.audit_id:
                trace_data = TraceCreate(
                    auditid=self.audit_id,
                    sequence=2,
                    component="Visual Generation Agent",
                    status="running",
                    input_data={
                        "sql": sql_query,
                        "query": msg,
                        "project_id": self.project_id,
                        "data_description": content['content'].get('data_description', 'This is default description').strip()
                    },
                    output_data=None,
                    time_taken=None
                )
                trace_response = await self.audit_service.create_trace(trace_data)
                trace_id = trace_response.trace_id
            
            url = f"{self.base_url}/sql-helper/summary"
            data = {
                "sql": sql_query,
                "query": msg,
                "project_id": self.project_id,
                "data_description": "I have given the sql query and question."
            }

            response = await self._make_api_request(url, data, "Followup")
            
            # Update trace as completed
            end_time = time.time()
            if trace_id and self.audit_id:
                if not (response.get("error")):
                    await self.audit_service.update_trace_status(
                        trace_id, 
                        "completed", 
                        response, 
                        end_time - start_time
                    )
                else:
                    await self.audit_service.update_trace_status(
                        trace_id, 
                        "failed", 
                        response, 
                        end_time - start_time
                    )
            
            return response

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error in _handle_followup_query: {e}\nTraceback: {error_traceback}")
            
            # Update trace as failed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "failed", 
                    {"error": str(e), "traceback": error_traceback}, 
                    end_time - start_time
                )
            
            return {
                "error": "Followup query failed",
                "details": str(e),
                "traceback": error_traceback
            }

    async def _handle_recommended_questions(self, content: Dict, thread_id: UUID, user_id: UUID, doc_id: List[str], message: ThreadMessage) -> Dict[str, Any]:
        """Handle recommended questions requests"""
        start_time = time.time()
        trace_id = None
        try:
            msg = content['content'].get('question', '').strip()
            if not msg:
                return {"error": "'question' field is required for recommended questions."}
            
            logger.info("Processing recommended questions")
            
            # Create trace for Recommended Questions Agent
            if self.audit_id:
                trace_data = TraceCreate(
                    auditid=self.audit_id,
                    sequence=3,
                    component="Recommended Questions Agent",
                    status="running",
                    input_data={"question": content['content'].get('question', '').strip()},
                    output_data=None,
                    time_taken=None
                )
                trace_response = await self.audit_service.create_trace(trace_data)
                trace_id = trace_response.trace_id
            
            url = f"{self.base_url}/recommendation/sqlrecommend"
            params = {
                "event_id": str(uuid4()),
                "user_question": msg,
                "project_id": self.project_id,
                "mdl": "mdl",
            }
            data = {
                    "configuration": {
                        "fiscal_year": {
                        "start": "string",
                        "end": "string"
                        },
                        "language": "English",
                        "timezone": {
                        "name": "UTC",
                        "utc_offset": ""
                        }
                    },
                    "previous_questions": []
                    }

            response = await self._make_api_request(url, data, "Recommended Questions", params=params)
            
            # Update trace as completed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "completed", 
                    response, 
                    end_time - start_time
                )
            
            return response

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error in _handle_recommended_questions: {e}\nTraceback: {error_traceback}")
            
            # Update trace as failed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "failed", 
                    {"error": str(e), "traceback": error_traceback}, 
                    end_time - start_time
                )
            
            return {
                "error": "Recommended questions failed",
                "details": str(e),
                "traceback": error_traceback
            }

    async def _handle_adjust_visual(self, content: Dict, thread_id: UUID, user_id: UUID, doc_id: List[str], message: ThreadMessage) -> Dict[str, Any]:
        """Handle visual adjustment requests"""
        start_time = time.time()
        trace_id = None
        try:
            msg = content['content'].get('question', '').strip()
            sql_query = content['content'].get('sql', '')
            adjustments = content['content'].get('adjustments', {})
            if isinstance(sql_query, list):
                sql_query=sql_query[0]
            
            if not msg or not sql_query:
                return {"error": "Both 'question' and 'sql' fields are required for visual adjustments."}
            
            logger.info("Processing visual adjustment")
            
            # Create trace for Visual Adjustment Agent
            if self.audit_id:
                trace_data = TraceCreate(
                    auditid=self.audit_id,
                    sequence=4,  # Assuming this comes after the main flow
                    component="Visual Adjustment Agent",
                    status="running",
                    input_data={
                        "query": msg,
                        "sql": sql_query,
                        "adjustments": adjustments
                    },
                    output_data=None,
                    time_taken=None
                )
                trace_response = await self.audit_service.create_trace(trace_data)
                trace_id = trace_response.trace_id
            
            url = f"{self.base_url}/chart-adjustment/adjust"
            data = {
                "query": msg,
                "sql": sql_query,
                "adjustment_option": {
                    "chart_type": adjustments.get("chart_type", "bar"),
                    "adjustment_option": adjustments.get("question"),
                    "x_axis": adjustments.get("x_axis", "string"),
                    "y_axis": adjustments.get("y_axis", "string"),
                    "x_offset": adjustments.get("x_offset", "string"),
                    "color": adjustments.get("color", "string"),
                    "theta": adjustments.get("theta", "string")
                },
                "chart_schema":  adjustments.get("chart_schema"),
                "project_id": self.project_id,
                "thread_id": str(thread_id),
                "configurations": {
                    "language": "English",
                    "timezone": {"name": "UTC", "utc_offset": ""}
                }
            }

            response = await self._make_api_request(url, data, "Visual Adjustment")
            
            # Update trace as completed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "completed", 
                    response, 
                    end_time - start_time
                )
            
            return response

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error in _handle_adjust_visual: {e}\nTraceback: {error_traceback}")
            
            # Update trace as failed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "failed", 
                    {"error": str(e), "traceback": error_traceback}, 
                    end_time - start_time
                )
            
            return {
                "error": "Visual adjustment failed",
                "details": str(e),
                "traceback": error_traceback
            }

    async def _handle_expand_query(self, content: Dict, thread_id: UUID, user_id: UUID, doc_id: List[str], message: ThreadMessage) -> Dict[str, Any]:
        """Handle expand query requests"""
        start_time = time.time()
        trace_id = None
        try:
            logger.info("Processing expand query")
            
            # Get original data from content or message
            original_query = content['content'].get('original_query', '')
            original_reasoning = content['content'].get('original_reasoning', '')
            sql_query = content['content'].get('sql', '')
            question = content['content'].get('question', '')
            
            # Create trace for Expand Agent
            if self.audit_id:
                trace_data = TraceCreate(
                    auditid=self.audit_id,
                    sequence=5,  # Assuming this comes after other operations
                    component="Expand Agent",
                    status="running",
                    input_data={
                        "query": question,
                        "sql": sql_query,
                        "original_query": original_query,
                        "original_reasoning": original_reasoning
                    },
                    output_data=None,
                    time_taken=None
                )
                trace_response = await self.audit_service.create_trace(trace_data)
                trace_id = trace_response.trace_id
            
            url = f"{self.base_url}/sql-helper/sql-expansion"
            data = {
                "query": question,
                "sql": sql_query,
                "original_query": original_query,
                "original_reasoning": original_reasoning,
                "project_id": self.project_id,
                "configuration": {"additionalProp1": {}},
                "schema_context": {"additionalProp1": {}}
            }

            # Get all responses for expand operation
            expand_response = await self._make_api_request(url, data, "Expand")
            content['content']['question'] = question
            content['content']['sqlquery'] = expand_response["data"]["expansion_suggestions"]["valid_results"][0].get("sql")
            # sql_response = await self._handle_sql_query(content, thread_id, user_id, doc_id)
            followup_response = await self._handle_followup_query(content, thread_id, user_id, doc_id, message)
            recommended_response = await self._handle_recommended_questions(content, thread_id, user_id, doc_id, message)

            final_response = {
                # "SQLResponse": sql_response,
                "FollowupResponse": followup_response,
                "RecommendedQuestions": recommended_response,
                "ExpandResponse": expand_response
            }

            # Update message response structure
            if message and message.response:
                # Move current to previous
                logger.info(f"type is {type(message.response)}")
                message.response["PreviousResponse"] = {
                    "SQLResponse": message.response["CurrentResponse"].get("SQLResponse"),
                    "FollowupResponse": message.response["CurrentResponse"].get("FollowupResponse"),
                    "RecommendedQuestions": message.response["CurrentResponse"].get("RecommendedQuestions"),
                    "CurrentAdjustments": message.response["CurrentResponse"].get("CurrentAdjustments")
                }
                
                # Set new current responses
                message.response["CurrentResponse"]["SQLResponse"] = expand_response
                message.response["CurrentResponse"]["FollowupResponse"] = followup_response
                message.response["CurrentResponse"]["RecommendedQuestions"] = recommended_response
                
                
                final_response = message.response 
            
            # Update trace as completed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "completed", 
                    final_response, 
                    end_time - start_time
                )
            
            return final_response

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error in _handle_expand_query: {e}\nTraceback: {error_traceback}")
            
            # Update trace as failed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "failed", 
                    {"error": str(e), "traceback": error_traceback}, 
                    end_time - start_time
                )
            
            return {
                "error": "Expand query failed",
                "details": str(e),
                "traceback": error_traceback
            }

    async def _handle_unstructered_query(self, content: Dict, thread_id: UUID, user_id: UUID, doc_id: List[str], message: ThreadMessage) -> Dict[str, Any]:
        """Handle unstructured query requests"""
        start_time = time.time()
        trace_id = None
        logger.info("Entered into _handle_unstructered_query")
        try:
            msg = content['content'].get('question', '').strip()
            api_name = "Unstructured"
            
            # Create trace for Unstructured Agent
            if self.audit_id:
                trace_data = TraceCreate(
                    auditid=self.audit_id,
                    sequence=1,
                    component="Unstructured Agent",
                    status="running",
                    input_data={
                        "prompt": msg,
                        "document_ids": doc_id
                    },
                    output_data=None,
                    time_taken=None
                )
                trace_response = await self.audit_service.create_trace(trace_data)
                trace_id = trace_response.trace_id
            
            url = f"{self.doc_url}/api/threads/chat"
            unique_thread_id = self.get_next_thread_id()
            data = {
                        "prompt": msg,
                        "thread_id": unique_thread_id,
                        "return_new_messages_only": True
                    }

            if doc_id:
                        data["document_ids"] = doc_id
            logger.info(f"payload {data},{unique_thread_id}")
            logger.info(f"[{api_name}] Sending request to: {url}")
            logger.debug(f"[{api_name}] Payload: {data}")
            response = await self._make_api_request(url, data, "unstructured")
            
            # Update trace as completed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "completed", 
                    response, 
                    end_time - start_time
                )
            
            return response
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Error in _handle_unstructered_query: {e}\nTraceback: {error_traceback}")
            
            # Update trace as failed
            end_time = time.time()
            if trace_id and self.audit_id:
                await self.audit_service.update_trace_status(
                    trace_id, 
                    "failed", 
                    {"error": str(e), "traceback": error_traceback}, 
                    end_time - start_time
                )
            
            return {
                "error": "Unstructured query failed",
                "details": str(e),
                "traceback": error_traceback
            }

    async def _make_api_request(self, url: str, data: Optional[Dict] = None, api_name: str = "API", params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP POST request with proper error handling"""
        try:
            logger.info(f"Making {api_name} POST request to: {url}")
            
            # timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            # Prepare request data - if data is None, use params as JSON body
            if api_name not in ("",""):
                headers = self.headers
            else:
                headers = self.doc_headers
            request_data = data if data is not None else None
            params = params if params is not None else None
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=request_data, headers=headers,params=params) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                            logger.info(f"{api_name} request successful")
                            return result
                        except json.JSONDecodeError:
                            logger.warning(f"{api_name} returned non-JSON response")
                            return {"response": response_text}
                    else:
                        logger.error(f"{api_name} request failed with status {response.status}: {response_text}")
                        return {
                            "error": f"{api_name} request failed",
                            "status_code": response.status,
                            "response": response_text
                        }

        except asyncio.TimeoutError:
            logger.error(f"{api_name} request timed out")
            return {
                "error": f"{api_name} request timed out",
                "timeout": self.timeout
            }
        except aiohttp.ClientError as e:
            logger.error(f"{api_name} client error: {e}")
            return {
                "error": f"{api_name} client error",
                "details": str(e)
            }
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.exception(f"Unexpected error in {api_name} request: {e}\nTraceback: {error_traceback}")
            return {
                "error": f"Unexpected error in {api_name} request",
                "details": str(e),
                "traceback": error_traceback
            }

    def __del__(self):
        """Cleanup method"""
        try:
            if hasattr(self, 'db') and self.db:
                self.db.close()
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")

    def get_next_thread_id(self):
        try:
            # Atomic increment to avoid race condition
            result = self.db.execute(
                text("""
                    UPDATE thread_id_tracker
                    SET last_thread_id = last_thread_id + 1
                    RETURNING last_thread_id
                """)
            )
            self.db.commit()
            return str(result.scalar())
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception("Failed to get next thread_id")
            raise

    def get_chat_history(self, thread_id: UUID, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history for a thread"""
        try:
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
        except Exception as e:
            logger.exception(f"Error getting chat history: {e}")
            return []

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
            try:
                await self._active_sessions[session_id].send_json(message)
            except Exception as e:
                logger.exception(f"Error broadcasting to session {session_id}: {e}")
                # Remove broken session
                self.unregister_session(session_id)

    async def handle_callback(self, message_id: UUID, response: Any):
        """Handle callback for async operations"""
        try:
            handler = self._message_handlers.get(str(message_id))
            if handler:
                await handler(response)
                self.unregister_message_handler(message_id)
        except Exception as e:
            logger.exception(f"Error handling callback for message {message_id}: {e}")