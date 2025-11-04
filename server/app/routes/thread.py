from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session,joinedload
from app.database import get_db
from app.models.user import User
from app.models.workspace import Project, ProjectAccess
from app.models.thread import Thread, ThreadCollaborator, ThreadConfiguration, Workflow
from app.models.team import Team, CollaborationRequest
from app.auth.okta import get_current_user
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from app.services.authorization import check_project_access
from app.services.thread_service import ThreadService
from app.schemas.thread import (
    ThreadCreate, Thread as ThreadSchema, WorkflowBase, Workflow as WorkflowSchema, WorkflowStep,
    NoteCreate, Note, TimelineCreate, Timeline, TimelineEvent, ThreadMessageCreate, ThreadMessage,
    ThreadCollaboratorCreate, ThreadCollaborator as ThreadCollaboratorSchema,
    ThreadCollaboratorUpdate, ThreadConfigurationCreate, ThreadConfiguration as ThreadConfigurationSchema,
    ThreadConfigurationUpdate,AddWorkflowRequest,WorkflowCreate,WorkflowType
)
from app.services.audit_service import AuditService
import traceback
from app.schemas.collaboration import CollaborationRequestCreate, CollaborationRequestResponse, CollaborationRequestRespond
from app.schemas.user import UserResponse, user_to_response
from app.utils.logger import logger, log_request, log_response, log_error
import json
import logging
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.sql import func

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = UUID('00000000-0000-0000-0000-000000000003')
DEFAULT_TEAM_ID = UUID('10000000-0000-0000-0000-000000000003')
DEFAULT_THREAD_CONFIG = {
    "allow_public_access": False,
    "max_collaborators": 10,
    "allowed_roles": ["owner", "collaborator", "viewer"],
    "default_role": "collaborator"
}

router = APIRouter(prefix="/threads", tags=["threads"])

class ThreadResponse(BaseModel):
    id: UUID
    project_id: UUID
    created_by: UUID
    title: str
    description: str
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] 
    is_active: bool
    workspace_id: Optional[UUID] = None
    workspace_name: Optional[str] = None 
    project_name: Optional[str] = None

class ThreadWorkflowResponse(BaseModel):
    id: str
    thread_id: Optional[str] = None
    thread_name: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    title: str
    description: Optional[str]
    steps: List[Dict[str, Any]]
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    creator: Optional[UserResponse] = None

    class Config:
        from_attributes = True

def thread_to_schema(thread) -> ThreadResponse:
    return ThreadResponse(
        id=thread.id,
        project_id=thread.project_id,
        created_by=thread.created_by,
        title=thread.title,
        description=thread.description,
        dataset_id=thread.dataset_id,
        dataset_name=thread.dataset_name,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        is_active=thread.is_active,
        workspace_id= thread.project.workspace.id,#getattr(thread, 'workspace_id', None),
        workspace_name=thread.project.workspace.name,
        project_name=thread.project.name
    )

def workflow_to_response(workflow: Workflow, db: Session) -> ThreadWorkflowResponse:
    creator = None
    if workflow.user:
        creator = user_to_response(workflow.user)

    thread = workflow.thread
    project = thread.project if thread else None
    workspace = project.workspace if project else None

    return ThreadWorkflowResponse(
        id=str(workflow.id),
        thread_id=str(thread.id) if thread else None,
        thread_name=thread.title if thread else None,
        project_id=str(project.id) if project else None,
        project_name=project.name if project else None,
        workspace_id=str(workspace.id) if workspace else None,
        workspace_name=workspace.name if workspace else None,
        title=workflow.title,
        description=workflow.description,
        steps=[step for step in workflow.steps],
        status=workflow.status,
        creator=creator,
        created_at=str(workflow.created_at) if workflow.created_at else None
    )

# --- Thread CRUD ---
@router.post("/", response_model=ThreadResponse)
async def create_thread(
    thread_data: ThreadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"Creating thread with data: {json.dumps(thread_data.dict(), default=str)}")
        logger.info(f"Current user ID: {current_user.id}")
        
        # Use default project ID if none provided
        project_id = thread_data.project_id or DEFAULT_PROJECT_ID
        
        # Check project access
        if not check_project_access(db, str(project_id), str(current_user.id)):
            logger.error(f"User {current_user.id} not authorized to create threads in project {project_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create threads in this project"
            )
        
        # Create thread with current user as creator
        service = ThreadService(db)
        thread = service.create_thread(ThreadCreate(
            dataset_id=thread_data.dataset_id,
            dataset_name=thread_data.dataset_name,
            project_id=project_id,
            created_by=str(current_user.id),  # Ensure user ID is string
            title=thread_data.title or "thread title",
            description=thread_data.description or "No description provided"
        ))
        
        logger.info(f"Successfully created thread {thread.id}")
        return thread_to_schema(thread)
        
    except Exception as e:
        logger.error(f"Error creating thread: {str(e)}")
        logger.error(f"Request data: {json.dumps(thread_data.dict(), default=str)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating thread: {str(e)}"
        )

@router.get("/audits_records")
async def get_audits(
    thread_id: Optional[UUID] =  Query(None),
    start_date: Optional[datetime] =  Query(None),
    end_date: Optional[datetime] = Query(None),
    cursor: Optional[str] = None,
    limit: Optional[int] = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        print("Entered API")

        service = AuditService(db)
        return await service.get_audit_records(
            user_id=str(current_user.id),
            thread_id=thread_id,
            start_date=start_date,
            end_date=end_date,
            cursor=cursor,
            limit=limit
        )
    except:
        traceback.print_exc()


@router.get("/all", response_model=List[ThreadResponse])
async def list_threads(
    project_id: Optional[UUID] = None,
    workspace_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all threads accessible to the user, including:
    1. Threads in specific project if project_id is provided
    2. Threads in specific workspace if workspace_id is provided
    3. Threads in all accessible projects
    4. Threads in default workspace/project
    """
    service = ThreadService(db)
    threads = service.list_threads_for_user(current_user, project_id, workspace_id)
    return [thread_to_schema(thread) for thread in threads]

@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    thread = service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if not check_project_access(db, str(thread.project_id), str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this thread")
    return thread_to_schema(thread)

@router.delete("/delete/Thread/{thread_id}")
async def delete_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
 
    if not thread:
        raise HTTPException(status_code=404, detail="Thread Not Found")
 
    try:
        db.delete(thread)
        db.commit()
        return {
            "message": "Thread is deleted successfully",
            "thread_id": thread.id,
            "threadName": thread.title
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

# --- Workflow Endpoints ---
@router.post("/{thread_id}/workflows", response_model=ThreadWorkflowResponse)
async def create_workflow(
    thread_id: UUID,
    workflow_data: WorkflowBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    thread = service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if not check_project_access(db, str(thread.project_id), str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this thread")
    
    id=uuid4()
    # Create workflow with current user as creator
    workflow = Workflow(
        id=id,
        thread_id=thread_id,
        user_id=current_user.id,  # Use current user's ID
        title=workflow_data.title,
        description=workflow_data.description,
        steps=[step.model_dump() for step in workflow_data.steps],
        status=workflow_data.status or "draft"
    )
    
    try:
        db.add(workflow)
        db.commit()
        db.refresh(workflow)  # This ensures we get the generated ID and timestamps
        logger.info(f"Successfully created workflow {workflow.id}")
        workflow_response = workflow_to_response(workflow, db)
        logger.info(f"Workflow response: {workflow_response}")
        return workflow_response
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating workflow: {str(e)}"
        )

@router.get("/{thread_id}/workflows", response_model=List[ThreadWorkflowResponse])
async def list_workflows(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    thread = service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if not check_project_access(db, str(thread.project_id), str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this thread")
    
    # Get workflows for the thread
    workflows = db.query(Workflow).filter(
        Workflow.thread_id == thread_id
    ).order_by(Workflow.created_at.desc()).all()
    
    return [workflow_to_response(w, db) for w in workflows]

@router.get("/workflows/{workflow_id}", response_model=ThreadWorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    # Check thread access
    service = ThreadService(db)
    thread = service.get_thread(workflow.thread_id)
    if not check_project_access(db, str(thread.project_id), str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this workflow")
    
    return workflow_to_response(workflow, db)

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    # Check if user is the creator or has admin access
    service = ThreadService(db)
    thread = service.get_thread(workflow.thread_id)
    # thread = ThreadService.get_thread(workflow.thread_id)
    if not check_project_access(db, str(thread.project_id), str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this workflow")
    
    # Only allow deletion by creator or thread owner
    if workflow.user_id != current_user.id and thread.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only workflow creator or thread owner can delete workflows")
    
    db.delete(workflow)
    db.commit()
    return {"message": "Workflow deleted successfully"}

@router.post("/{thread_id}/workflows/{workflow_id}/steps", response_model=ThreadWorkflowResponse)
async def add_workflow_step(
    thread_id: UUID,    
    workflow_id: UUID,
    step: WorkflowStep,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id and Workflow.thread_id == thread_id).first()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    # Check thread access
    service = ThreadService(db)
    thread = service.get_thread(workflow.thread_id)
    if not check_project_access(db, str(thread.project_id), str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this workflow")
    
    # Add step to workflow
    steps = workflow.steps or []
    steps.append(step.model_dump())
    workflow.steps = steps
    workflow.updated_at = func.now()
    
    db.commit()
    db.refresh(workflow)
    return workflow_to_response(workflow, db)

# --- Note Endpoints ---
@router.post("/{thread_id}/notes", response_model=Note)
async def create_note(
    thread_id: UUID,
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.create_note_for_user(thread_id, note_data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/{thread_id}/notes", response_model=List[Note])
async def list_notes(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.list_notes_for_user(thread_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/{thread_id}/notes/reorder", response_model=List[Note])
async def reorder_notes(
    thread_id: UUID,
    note_orders: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.reorder_notes_for_user(thread_id, note_orders, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

# --- Timeline Endpoints ---
@router.post("/{thread_id}/timelines", response_model=Timeline)
async def create_timeline(
    thread_id: UUID,
    timeline_data: TimelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.create_timeline_for_user(thread_id, timeline_data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/{thread_id}/timelines", response_model=List[Timeline])
async def list_timelines(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.list_timelines_for_user(thread_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/timelines/{timeline_id}/events", response_model=Timeline)
async def add_timeline_event(
    timeline_id: UUID,
    event: TimelineEvent,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.add_timeline_event_for_user(timeline_id, event, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/{thread_id}/timelines/reorder", response_model=List[Timeline])
async def reorder_timelines(
    thread_id: UUID,
    timeline_orders: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.reorder_timelines_for_user(thread_id, timeline_orders, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/{thread_id}/collaborators", response_model=ThreadCollaboratorSchema)
async def add_thread_collaborator(
    thread_id: UUID,
    data: ThreadCollaboratorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        log_request(logger, f"POST /threads/{thread_id}/collaborators", data.dict())
        
        thread = db.query(Thread).filter(Thread.id == thread_id).first()
        if not thread:
            log_error(logger, f"POST /threads/{thread_id}/collaborators", 
                     HTTPException(status_code=404, detail="Thread not found"))
            raise HTTPException(status_code=404, detail="Thread not found")
            
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            log_error(logger, f"POST /threads/{thread_id}/collaborators",
                     HTTPException(status_code=403, detail="Not authorized to add collaborators to this thread"))
            raise HTTPException(status_code=403, detail="Not authorized to add collaborators to this thread")
        
        service = ThreadService(db)
        response_data = service.add_collaborator(thread_id, data)
        
        log_response(logger, f"POST /threads/{thread_id}/collaborators", response_data)
        return response_data
        
    except ValueError as e:
        log_error(logger, f"POST /threads/{thread_id}/collaborators", e, data.dict())
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error(logger, f"POST /threads/{thread_id}/collaborators", e, data.dict())
        raise

@router.get("/{thread_id}/collaborators", response_model=List[UserResponse])
async def list_thread_collaborators(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.list_thread_collaborators(thread_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.put("/collaborators/{collaborator_id}", response_model=ThreadCollaboratorSchema)
async def update_collaborator_status(
    collaborator_id: UUID,
    data: ThreadCollaboratorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        log_request(logger, f"PUT /threads/collaborators/{collaborator_id}", data.dict())
        
        collaborator = db.query(ThreadCollaborator).filter(ThreadCollaborator.id == collaborator_id).first()
        if not collaborator:
            log_error(logger, f"PUT /threads/collaborators/{collaborator_id}",
                     HTTPException(status_code=404, detail="Collaborator not found"))
            raise HTTPException(status_code=404, detail="Collaborator not found")
        
        thread = db.query(Thread).filter(Thread.id == collaborator.thread_id).first()
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            log_error(logger, f"PUT /threads/collaborators/{collaborator_id}",
                     HTTPException(status_code=403, detail="Not authorized to update this collaborator"))
            raise HTTPException(status_code=403, detail="Not authorized to update this collaborator")
        
        service = ThreadService(db)
        updated_collaborator = service.update_collaborator(collaborator_id, data)
        
        log_response(logger, f"PUT /threads/collaborators/{collaborator_id}", updated_collaborator.__dict__)
        return updated_collaborator
        
    except ValueError as e:
        log_error(logger, f"PUT /threads/collaborators/{collaborator_id}", e, data.dict())
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error(logger, f"PUT /threads/collaborators/{collaborator_id}", e, data.dict())
        raise

@router.post("/{thread_id}/configurations", response_model=ThreadConfigurationSchema)
async def create_thread_configuration(
    thread_id: UUID,
    data: ThreadConfigurationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"Creating configuration for thread {thread_id}")
        logger.info(f"Request data: {json.dumps(data.dict(), default=str)}")
        
        thread = db.query(Thread).filter(Thread.id == thread_id).first()
        if not thread:
            logger.error(f"Thread {thread_id} not found")
            raise HTTPException(status_code=404, detail="Thread not found")
            
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            logger.error(f"User {current_user.id} not authorized to configure thread {thread_id}")
            raise HTTPException(status_code=403, detail="Not authorized to configure this thread")
        
        service = ThreadService(db)
        config = service.create_configuration(thread_id, data)
        
        logger.info(f"Successfully created configuration {config.id} for thread {thread_id}")
        return config
        
    except ValueError as e:
        logger.error(f"Error creating thread configuration: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating thread configuration: {str(e)}")
        raise

@router.get("/{thread_id}/configurations", response_model=List[ThreadConfigurationSchema])
async def list_thread_configurations(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        thread = db.query(Thread).filter(Thread.id == thread_id).first()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            raise HTTPException(status_code=403, detail="Not authorized to access this thread")
        
        service = ThreadService(db)
        configs = service.get_configurations(thread_id)
        return configs
    except Exception as e:
        logger.error(f"Error listing thread configurations: {str(e)}")
        raise

@router.get("/{thread_id}/configurations/default", response_model=ThreadConfigurationSchema)
async def get_default_configuration(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        thread = db.query(Thread).filter(Thread.id == thread_id).first()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        if not check_project_access(db, str(thread.project_id), str(current_user.id)):
            raise HTTPException(status_code=403, detail="Not authorized to access this thread")
        
        service = ThreadService(db)
        config = service.get_default_configuration(thread_id)
        return config
    except Exception as e:
        logger.error(f"Error getting default configuration: {str(e)}")
        raise

@router.post("/collaboration_requests/{request_id}/respond", response_model=ThreadCollaboratorSchema)
async def respond_to_collaboration_request(
    request_id: UUID,
    data: ThreadCollaboratorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.respond_to_collaboration_request(request_id, current_user, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{thread_id}/collaboration_requests", response_model=List[ThreadCollaboratorSchema])
async def list_collaboration_requests(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        return service.list_collaboration_requests(thread_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/{thread_id}/search-collaborators", response_model=Dict[str, Any])
async def search_collaborators(
    thread_id: UUID,
    offset: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ThreadService(db)
    try:
        users, has_more = service.search_collaborators(thread_id, offset=offset, limit=limit)
        return {
            "users": [user_to_response(u) for u in users],
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 
    

@router.get("/allWorkflows/all")
async def get_all_workflows_for_currentUser(db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
   
    allWorkFlows = db.query(Workflow).options(
        joinedload(Workflow.thread)
            .joinedload(Thread.project)
            .joinedload(Project.workspace)
    ).filter(Workflow.user_id == current_user.id).all()
 
    return [
        {
            "workFlowId": flow.id,
            "workFlowName": flow.title,
            "workFlowDescription": flow.description,
            "Steps": flow.steps,
            "publishedAs": {"isDashboard" : flow.is_dashboard, "isReport":flow.is_report, "isAlert":flow.is_alert},
            "threadId": str(flow.thread.id) if flow.thread else None,
            "threadName": flow.thread.title if flow.thread else None,
            "projectId": flow.thread.project.id if flow.thread and flow.thread.project else None,
            "projectName": flow.thread.project.name if flow.thread and flow.thread.project else None,
            "workspaceId": flow.thread.project.workspace.id if flow.thread and flow.thread.project and flow.thread.project.workspace else None,
            "workspaceName": flow.thread.project.workspace.name if flow.thread and flow.thread.project and flow.thread.project.workspace else None,
            "createdAt": str(flow.created_at)
        }
        for flow in allWorkFlows
    ]  
 
@router.post("/addWorkflow/")
async def add_workflow(request: AddWorkflowRequest, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    """
    Add a workflow by updating the corresponding boolean field based on workflow type
    """
    try:
        service = ThreadService(db)
        return service.add_workflow_to_editors(request,current_user)
        # Find the workflow by ID
       
       
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating workflow: {str(e)}")


@router.get("/getAddedWorkflows/{workflow_type}/")
def get_added_workflows(workflow_type: WorkflowType, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    """
    Get all workflows filtered by type based on their boolean flags
    """
    try:
        service = ThreadService(db)
        return service.get_all_workflow_to_Editors(workflow_type,current_user)
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching workflows: {str(e)}")

