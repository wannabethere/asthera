from typing import List, Optional, Dict, Any,Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session,joinedload  
from app.models.thread import Thread, ThreadMessage, Workflow, Note, Timeline, ThreadCollaborator, ThreadConfiguration
from app.schemas.thread import (
    ThreadCreate,
    ThreadMessageCreate,
    WorkflowCreate,
    NoteBase,
    TimelineCreate,
    WorkflowStep,
    TimelineEvent,
    ThreadCollaboratorCreate,
    ThreadCollaboratorUpdate,
    ThreadConfigurationCreate,
    ThreadConfigurationUpdate,
    AddWorkflowRequest,WorkflowType
)
from app.models.team import CollaborationRequest
from app.models.user import User
from app.services.authorization import check_project_access
from app.utils.logger import logger
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import json
from app.models.workspace import Workspace,Project
from app.models.workspace import Project, ProjectAccess
from fastapi import HTTPException
import traceback
import logging
from sqlalchemy.exc import SQLAlchemyError
 
# Set up logging
logger = logging.getLogger(__name__)

class ThreadService:
    def __init__(self, db: Session):
        self.db = db

    def create_thread(self, thread_data: ThreadCreate) -> Thread:
        """Create a new thread"""
        try:
            thread = Thread(
                dataset_id=thread_data.dataset_id,
                dataset_name=thread_data.dataset_name,
                project_id=thread_data.project_id,
                created_by=thread_data.created_by,
                title=thread_data.title,
                description=thread_data.description
            )
            self.db.add(thread)
            self.db.commit()
            self.db.refresh(thread)
            return thread
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating thread: {str(e)}")
            raise

    def get_thread(self, thread_id: UUID) -> Optional[Thread]:
        """Get thread by ID"""
        return self.db.query(Thread).options(joinedload  (Thread.project).joinedload  (Project.workspace)).filter(Thread.id == thread_id).first()

    def add_collaborator(self, thread_id: UUID, data: ThreadCollaboratorCreate) -> Dict[str, Any]:
        """Add a collaborator to a thread"""
        try:
            thread = self.get_thread(thread_id)
            if not thread:
                raise ValueError("Thread not found")

            # Check if collaborator already exists
            existing = self.db.query(ThreadCollaborator).filter(
                ThreadCollaborator.thread_id == thread_id,
                ThreadCollaborator.user_id == data.user_id
            ).first()
            if existing:
                raise ValueError("User is already a collaborator")

            # Create new collaborator
            collaborator = ThreadCollaborator(
                id=uuid4(),
                thread_id=thread_id,
                user_id=data.user_id,
                role=data.role,
                message=data.message,
                data_connection={"dummy": "test"},
                status='pending'
            )
            self.db.add(collaborator)
            self.db.commit()
            self.db.refresh(collaborator)

            # Create response data
            response_data = {
                "id": str(collaborator.id),
                "user_id": str(collaborator.user_id),
                "role": collaborator.role,
                "message": collaborator.message,
                "status": collaborator.status,
                "data_connection": {"dummy": "test"}
            }
            return response_data

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding collaborator: {str(e)}")
            raise

    def update_collaborator(self, collaborator_id: UUID, data: ThreadCollaboratorUpdate) -> ThreadCollaborator:
        """Update collaborator status"""
        try:
            collaborator = self.db.query(ThreadCollaborator).filter(
                ThreadCollaborator.id == collaborator_id
            ).first()
            if not collaborator:
                raise ValueError("Collaborator not found")

            if data.status:
                collaborator.status = data.status
            if data.role:
                collaborator.role = data.role
            if data.message:
                collaborator.message = data.message
            if data.data_connection:
                collaborator.data_connection = data.data_connection

            self.db.commit()
            self.db.refresh(collaborator)
            return collaborator

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating collaborator: {str(e)}")
            raise

    def get_collaborators(self, thread_id: UUID) -> List[User]:
        """Get all collaborators for a thread"""
        try:
            thread = self.get_thread(thread_id)
            if not thread:
                raise ValueError("Thread not found")

            # Get accepted collaborators
            collaborators = self.db.query(ThreadCollaborator).filter(
                ThreadCollaborator.thread_id == thread_id,
                ThreadCollaborator.status == 'accepted'
            ).all()

            user_ids = [c.user_id for c in collaborators]
            # Always include thread creator
            user_ids.append(thread.created_by)
            users = self.db.query(User).filter(User.id.in_(user_ids)).all()
            return users

        except Exception as e:
            logger.error(f"Error getting collaborators: {str(e)}")
            raise

    def create_configuration(self, thread_id: UUID, data: ThreadConfigurationCreate) -> ThreadConfiguration:
        """Create thread configuration"""
        try:
            thread = self.get_thread(thread_id)
            if not thread:
                raise ValueError("Thread not found")

            # If this is set as default, unset any existing default
            if data.is_default:
                existing_default = self.db.query(ThreadConfiguration).filter(
                    ThreadConfiguration.thread_id == thread_id,
                    ThreadConfiguration.is_default == True
                ).first()
                if existing_default:
                    existing_default.is_default = False
                    self.db.commit()

            config = ThreadConfiguration(
                thread_id=thread_id,
                name=data.name,
                config=data.config,
                is_default=data.is_default
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            return config

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating thread configuration: {str(e)}")
            raise

    def get_configurations(self, thread_id: UUID) -> List[ThreadConfiguration]:
        """Get all configurations for a thread"""
        try:
            thread = self.get_thread(thread_id)
            if not thread:
                raise ValueError("Thread not found")

            configs = self.db.query(ThreadConfiguration).filter(
                ThreadConfiguration.thread_id == thread_id
            ).all()
            return configs

        except Exception as e:
            logger.error(f"Error getting thread configurations: {str(e)}")
            raise

    def get_default_configuration(self, thread_id: UUID) -> ThreadConfiguration:
        """Get default configuration for a thread"""
        try:
            thread = self.get_thread(thread_id)
            if not thread:
                raise ValueError("Thread not found")

            config = self.db.query(ThreadConfiguration).filter(
                ThreadConfiguration.thread_id == thread_id,
                ThreadConfiguration.is_default == True
            ).first()

            if not config:
                # Create default configuration if none exists
                config = ThreadConfiguration(
                    thread_id=thread_id,
                    name="Default Configuration",
                    config={
                        "allow_public_access": False,
                        "max_collaborators": 10,
                        "allowed_roles": ["owner", "collaborator", "viewer"],
                        "default_role": "collaborator"
                    },
                    is_default=True
                )
                self.db.add(config)
                self.db.commit()
                self.db.refresh(config)

            return config

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error getting default configuration: {str(e)}")
            raise

    def add_message(self, thread_id: UUID, message_data: ThreadMessageCreate) -> ThreadMessage:
        """Add a new message to a thread"""
        message = ThreadMessage(
            thread_id=thread_id,
            user_id=message_data.user_id,
            content=message_data.content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_messages(self, thread_id: UUID) -> List[ThreadMessage]:
        """Get all messages for a thread"""
        return self.db.query(ThreadMessage).filter(
            ThreadMessage.thread_id == thread_id
        ).order_by(ThreadMessage.created_at).all()

    def create_workflow(self, thread_id: UUID, workflow_data: WorkflowCreate,userId) -> Workflow:
        """Create a new workflow in a thread"""
        workflow = Workflow(
            thread_id=thread_id,
            user_id=userId,
            title=workflow_data.title,
            description=workflow_data.description,
            steps=[step.model_dump() for step in workflow_data.steps],
            status=workflow_data.status
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def get_workflows(self, thread_id: UUID) -> List[Workflow]:
        """Get all workflows for a thread"""
        return self.db.query(Workflow).filter(
            Workflow.thread_id == thread_id
        ).order_by(Workflow.created_at).all()

    def add_workflow_step(self, workflow_id: UUID, step: WorkflowStep) -> Workflow:
        """Add a new step to an existing workflow"""
        
        workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
        print("workFlow steps",workflow.steps)
        if workflow:
            current_steps = workflow.steps or []
            
            current_steps.append(step.model_dump())
            
            workflow.steps = current_steps
            
            self.db.commit()
            self.db.refresh(workflow)
        return {
  "title": workflow.title,
  "description": workflow.description,
  "steps": workflow.steps,
  "status": "draft",
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "thread_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "created_at": "2025-05-19T19:03:16.336Z",
  "updated_at": "2025-05-19T19:03:16.336Z"
}

    def create_note(self, thread_id: UUID, note_data: NoteBase,userid) -> Note:
        """Create a new note in a thread"""
        # Get the highest sortorder value for existing notes
        max_sortorder = self.db.query(Note).filter(
            Note.thread_id == thread_id
        ).order_by(Note.sortorder.desc()).first()
        
        new_sortorder = (max_sortorder.sortorder + 1) if max_sortorder else 0
        
        note = Note(
            thread_id=thread_id,
            user_id=userid,
            title=note_data.title,
            content=note_data.content,
            sortorder=new_sortorder
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_notes(self, thread_id: UUID) -> List[Note]:
        """Get all notes for a thread in order"""
        return self.db.query(Note).filter(
            Note.thread_id == thread_id
        ).order_by(Note.sortorder).all()

    def reorder_notes(self, thread_id: UUID, note_orders: Dict[UUID, int]) -> List[Note]:
        """Reorder notes in a thread"""
        notes = self.db.query(Note).filter(
            Note.thread_id == thread_id,
            Note.id.in_(note_orders.keys())
        ).all()
        
        for note in notes:
            note.sortorder = note_orders[note.id]
        
        self.db.commit()
        return self.get_notes(thread_id)

    def create_timeline(self, thread_id: UUID, timeline_data: TimelineCreate) -> Timeline:
        """Create a new timeline in a thread"""
        # Get the highest sortorder value for existing timelines
        max_sortorder = self.db.query(Timeline).filter(
            Timeline.thread_id == thread_id
        ).order_by(Timeline.sortorder.desc()).first()
        
        new_sortorder = (max_sortorder.sortorder + 1) if max_sortorder else 0
        
        timeline = Timeline(
            thread_id=thread_id,
            user_id=timeline_data.user_id,
            title=timeline_data.title,
            description=timeline_data.description,
            events=timeline_data.events,
            sortorder=new_sortorder
        )
        self.db.add(timeline)
        self.db.commit()
        self.db.refresh(timeline)
        return timeline

    def get_timelines(self, thread_id: UUID) -> List[Timeline]:
        """Get all timelines for a thread in order"""
        return self.db.query(Timeline).filter(
            Timeline.thread_id == thread_id
        ).order_by(Timeline.sortorder).all()

    def add_timeline_event(self, timeline_id: UUID, event: TimelineEvent) -> Timeline:
        """Add a new event to an existing timeline"""
        timeline = self.db.query(Timeline).filter(Timeline.id == timeline_id).first()
        if timeline:
            current_events = timeline.events or []
            current_events.append(event.dict())
            timeline.events = current_events
            self.db.commit()
            self.db.refresh(timeline)
        return timeline

    def reorder_timelines(self, thread_id: UUID, timeline_orders: Dict[UUID, int]) -> List[Timeline]:
        """Reorder timelines in a thread"""
        timelines = self.db.query(Timeline).filter(
            Timeline.thread_id == thread_id,
            Timeline.id.in_(timeline_orders.keys())
        ).all()
        
        for timeline in timelines:
            timeline.sortorder = timeline_orders[timeline.id]
        
        self.db.commit()
        return self.get_timelines(thread_id)

    def send_invite_email(self, to_email: str, thread_id: str, inviter: str = None, message: str = None):
        # Placeholder: Replace with your actual SMTP config and email template
        from_email = "noreply@example.com"
        subject = "You're invited to collaborate on a thread"
        body = f"You have been invited to collaborate on thread {thread_id}."
        if inviter:
            body = f"{inviter} has invited you to collaborate on thread {thread_id}."
        if message:
            body += f"\n\nMessage: {message}"
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = formataddr(("ComplianceSpark", from_email))
        msg['To'] = to_email
        # Example: send via localhost SMTP (customize as needed)
        try:
            with smtplib.SMTP('localhost') as server:
                server.sendmail(from_email, [to_email], msg.as_string())
        except Exception as e:
            print(f"Failed to send invite email: {e}")

    def list_threads_for_user(self, user: User, project_id: Optional[UUID] = None, workspace_id: Optional[UUID] = None) -> List[Any]:
        """List all threads accessible to the user, optionally filtered by project or workspace."""
        print("ProjectID from the start",project_id)
        project_ids = set()
        # DEFAULT_PROJECT_ID = UUID('00000000-0000-0000-0000-000000000003')
        # project_ids.add(DEFAULT_PROJECT_ID) this section is removed because user doesn't needs to access default one because when a user is created automatically a project is creating.
        print("projectID before i am starting",project_ids)

        # If specific project_id is provided, check access and add it
        if project_id:
            if check_project_access(self.db, str(project_id), str(user.id)):
                project_ids.add(project_id)
                print("projectID in if peoject",project_ids)
            else:
                return []

        # If workspace_id is provided, get all projects in that workspace
        if workspace_id:
            workspace_projects = self.db.query(Project).filter(
                Project.workspace_id == workspace_id
            ).all()
            for project in workspace_projects:
                if check_project_access(self.db, str(project.id), str(user.id)):
                    project_ids.add(project.id)
                    print("projectID in if workspace if",project_ids)

        # Get all projects the user has access to
        accessible_projects = self.db.query(Project).join(
            ProjectAccess, Project.id == ProjectAccess.project_id
        ).filter(ProjectAccess.user_id == str(user.id)).all()
        for project in accessible_projects:
            project_ids.add(project.id)
            print("projectID in if Compleye",project_ids)

        # Get all threads from the collected project IDs
        threads = self.db.query(Thread).filter(
            Thread.project_id.in_(list(project_ids))
        ).all()

        # Add workspace and project information to each thread (as attributes)
        for thread in threads:
            project = self.db.query(Project).filter(Project.id == thread.project_id).first()
            if project:
                thread.workspace_id = project.workspace_id
                thread.workspace_name = project.workspace.name if project.workspace else None
                thread.project_name = project.name
        print("Threads",threads)
        return threads

    def list_thread_collaborators(self, thread_id: UUID, user: User) -> List[Any]:
        """List all collaborators for a thread, as UserResponse."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        # Only return if user has access
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        users = self.get_collaborators(thread_id)
        from app.schemas.user import user_to_response
        return [user_to_response(u) for u in users]

    def respond_to_collaboration_request(self, request_id: UUID, user: User, data: Any) -> Any:
        """Respond to a thread collaboration request."""
        collaborator = self.db.query(ThreadCollaborator).filter(
            ThreadCollaborator.id == request_id,
            ThreadCollaborator.user_id == user.id
        ).first()
        if not collaborator:
            raise ValueError("Collaboration request not found")
        if collaborator.status != 'pending':
            raise ValueError("Request already responded to")
        if data.status not in ['accepted', 'rejected']:
            raise ValueError("Status must be either 'accepted' or 'rejected'")
        collaborator.status = data.status
        if hasattr(data, 'message') and data.message:
            collaborator.message = data.message
        if hasattr(data, 'role') and data.role:
            collaborator.role = data.role
        if hasattr(data, 'data_connection') and data.data_connection:
            collaborator.data_connection = data.data_connection
        self.db.commit()
        self.db.refresh(collaborator)
        return collaborator

    def list_collaboration_requests(self, thread_id: UUID, user: User) -> List[Any]:
        """List collaboration requests for the current user in a thread."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        # if not check_project_access(self.db, str(thread.project_id), str(user.id)):
        #     raise PermissionError("Not authorized to access this thread")
        requests = self.db.query(ThreadCollaborator).filter(
            ThreadCollaborator.thread_id == thread_id,
            ThreadCollaborator.user_id == user.id,
            ThreadCollaborator.status == 'pending'
        ).all()
        return requests

    def create_note_for_user(self, thread_id: UUID, note_data: Any, user: User) -> Any:
        """Create a new note in a thread, with error handling and response schema."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        note = self.create_note(thread_id, note_data,user.id)
        from app.schemas.thread import Note
        return Note.from_orm(note)

    def list_notes_for_user(self, thread_id: UUID, user: User) -> list:
        """List all notes for a thread, as response models."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        notes = self.get_notes(thread_id)
        from app.schemas.thread import Note
        return [Note.from_orm(n) for n in notes]

    def reorder_notes_for_user(self, thread_id: UUID, note_orders: dict, user: User) -> list:
        """Reorder notes in a thread, as response models."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        notes = self.reorder_notes(thread_id, note_orders)
        from app.schemas.thread import Note
        return [Note.from_orm(n) for n in notes]

    def create_timeline_for_user(self, thread_id: UUID, timeline_data: Any, user: User) -> Any:
        """Create a new timeline in a thread, with error handling and response schema."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        timeline = self.create_timeline(thread_id, timeline_data)
        from app.schemas.thread import Timeline
        return Timeline.from_orm(timeline)

    def list_timelines_for_user(self, thread_id: UUID, user: User) -> list:
        """List all timelines for a thread, as response models."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        timelines = self.get_timelines(thread_id)
        from app.schemas.thread import Timeline
        return [Timeline.from_orm(t) for t in timelines]

    def add_timeline_event_for_user(self, timeline_id: UUID, event: Any, user: User) -> Any:
        """Add a new event to a timeline, with error handling and response schema."""
        from app.models.thread import Timeline as TimelineModel
        timeline = self.db.query(TimelineModel).filter(TimelineModel.id == timeline_id).first()
        if not timeline:
            raise ValueError("Timeline not found")
        thread = self.get_thread(timeline.thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this timeline")
        updated_timeline = self.add_timeline_event(timeline_id, event)
        from app.schemas.thread import Timeline
        return Timeline.from_orm(updated_timeline)

    def reorder_timelines_for_user(self, thread_id: UUID, timeline_orders: dict, user: User) -> list:
        """Reorder timelines in a thread, as response models."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        timelines = self.reorder_timelines(thread_id, timeline_orders)
        from app.schemas.thread import Timeline
        return [Timeline.from_orm(t) for t in timelines]

    def create_configuration_for_user(self, thread_id: UUID, data: Any, user: User) -> Any:
        """Create a thread configuration with error handling and response schema."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to configure this thread")
        config = self.create_configuration(thread_id, data)
        from app.schemas.thread import ThreadConfiguration
        return ThreadConfiguration.from_orm(config)

    def list_configurations_for_user(self, thread_id: UUID, user: User) -> list:
        """List all configurations for a thread, as response models."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        configs = self.get_configurations(thread_id)
        from app.schemas.thread import ThreadConfiguration
        return [ThreadConfiguration.from_orm(c) for c in configs]

    def get_default_configuration_for_user(self, thread_id: UUID, user: User) -> Any:
        """Get the default configuration for a thread, as a response model."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
        config = self.get_default_configuration(thread_id)
        from app.schemas.thread import ThreadConfiguration
        return ThreadConfiguration.from_orm(config) 
    def search_collaborators(self, thread_id: UUID, offset: int = 0, limit: int = 20) -> Tuple[List[User], bool]:
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError("Thread not found")
        project = self.db.query(Project).filter(Project.id == thread.project_id).first()
        if not project:
            raise ValueError("Project not found")
        # Default IDs
        DEFAULT_PROJECT_ID = UUID('00000000-0000-0000-0000-000000000003')
        DEFAULT_WORKSPACE_ID = UUID('00000000-0000-0000-0000-000000000003')
        is_default = (project.id == DEFAULT_PROJECT_ID) or (project.workspace_id == DEFAULT_WORKSPACE_ID)
        query = self.db.query(User)
        if not is_default:
            # Only users with access to this project
            user_ids = [pa.user_id for pa in self.db.query(ProjectAccess).filter(ProjectAccess.project_id == project.id)]
            query = query.filter(User.id.in_(user_ids))
        # Pagination
        total = query.count()
        users = query.offset(offset).limit(limit).all()
        has_more = (offset + limit) < total
        return users, has_more 
    
    
    def add_workflow_to_editors(self, request: AddWorkflowRequest,current_user):
        """
        Add workflow to editors with comprehensive error handling and logging
        """
        try:
            # Find the workflow by ID and user_id
            workflow = self.db.query(Workflow).filter(
                Workflow.id == request.workflow_id,
                Workflow.user_id == current_user.id
            ).first()
           
            if not workflow:
                logger.warning(f"Workflow not found: ID={request.workflow_id}, User={current_user.id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Workflow with ID {request.workflow_id} not found or you don't have permission to access it"
                )
           
            # Store original state for rollback reference
            original_state = {
                'is_dashboard': workflow.is_dashboard,
                'is_report': workflow.is_report,
                'is_alert': workflow.is_alert
            }
           
            # Update the appropriate field based on workflow type
            if request.workflow_type == WorkflowType.DASHBOARD:
                workflow.is_dashboard = True
                logger.info(f"Setting is_dashboard=True for workflow {request.workflow_id}")
            elif request.workflow_type == WorkflowType.REPORT:
                workflow.is_report = True
                logger.info(f"Setting is_report=True for workflow {request.workflow_id}")
            elif request.workflow_type == WorkflowType.ALERTS:
                workflow.is_alert = True
                logger.info(f"Setting is_alerts=True for workflow {request.workflow_id}")
            else:
                logger.error(f"Invalid workflow type: {request.workflow_type}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid workflow type: {request.workflow_type}"
                )
           
            # Save to database
            self.db.commit()
            self.db.refresh(workflow)
           
            logger.info(f"Successfully added workflow {request.workflow_id} to {request.workflow_type.value}")
           
            return {
                "message": f"Workflow {request.workflow_id} successfully added to {request.workflow_type.value}",
                "workflow_id": workflow.id,
                "workflow_type": request.workflow_type.value,
                "updated": True,
                "previous_state": original_state
            }
           
        except HTTPException:
            # Re-raise HTTP exceptions without modification
            raise
           
        except SQLAlchemyError as e:
            # Handle database-specific errors
            self.db.rollback()
            error_msg = f"Database error while updating workflow {request.workflow_id}"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
           
            raise HTTPException(
                status_code=500,
                detail=f"Database error occurred. Please try again later. Error ID: {id(e)}"
            )
           
        except AttributeError as e:
            # Handle cases where workflow object might be None or missing attributes
            self.db.rollback()
            error_msg = f"Attribute error while processing workflow {request.workflow_id}"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
           
            raise HTTPException(
                status_code=500,
                detail="Internal server error: Invalid workflow data structure"
            )
           
        except ValueError as e:
            # Handle value-related errors (e.g., invalid enum values)
            self.db.rollback()
            error_msg = f"Value error while processing workflow {request.workflow_id}"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
           
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request data: {str(e)}"
            )
           
        except Exception as e:
            # Catch-all for any other unexpected errors
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
                logger.error(f"Rollback traceback: {traceback.format_exc()}")
           
            error_id = id(e)  # Generate unique error ID for tracking
            error_msg = f"Unexpected error while updating workflow {request.workflow_id}"
           
            logger.error(f"{error_msg} (Error ID: {error_id}): {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
           
            # Log request details for debugging
            logger.error(f"Request details - Workflow ID: {request.workflow_id}, Type: {request.workflow_type}")
            logger.error(f"User ID: {getattr(current_user, 'id', 'Unknown')}")
           
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred. Please contact support with Error ID: {error_id}"
            )
 

    def get_all_workflow_to_Editors(self, workflow_type: WorkflowType, current_user):
        """
        Get all workflows filtered by type and user with comprehensive error handling
       
        Args:
            workflow_type: The type of workflow to filter by
            current_user: The current authenticated user
           
        Returns:
            List of workflows matching the criteria
           
        Raises:
            HTTPException: For client errors (400, 404) or server errors (500)
        """
        try:
            # Input validation
            if not workflow_type:
                logger.warning("Workflow type is None or empty")
                raise HTTPException(
                    status_code=400,
                    detail="Workflow type is required"
                )
               
            if not current_user or not hasattr(current_user, 'id'):
                logger.warning("Invalid or missing current_user")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required - invalid user"
                )
           
            # Log the request
            logger.info(f"Fetching {workflow_type.value} workflows for user {current_user.id}")
           
            # Initialize query
            query = (
            self.db.query(Workflow)
            .options(
                joinedload(Workflow.thread)
                .joinedload(Thread.project)
                .joinedload(Project.workspace)
            )
        )
           
            # Filter based on workflow type and user
            if workflow_type == WorkflowType.DASHBOARD:
                workflows = query.filter(
                    Workflow.is_dashboard == True,
                    Workflow.user_id == current_user.id
                ).all()
                logger.debug(f"Found {len(workflows)} dashboard workflows for user {current_user.id}")
               
            elif workflow_type == WorkflowType.REPORT:
                workflows = query.filter(
                    Workflow.is_report == True,
                    Workflow.user_id == current_user.id
                ).all()
                logger.debug(f"Found {len(workflows)} report workflows for user {current_user.id}")
               
            elif workflow_type == WorkflowType.ALERTS:
                # Note: Fixed potential typo - using is_alerts instead of is_alert
                workflows = query.filter(
                    Workflow.is_alert == True,  # or is_alert if that's your actual column name
                    Workflow.user_id == current_user.id
                ).all()
                logger.debug(f"Found {len(workflows)} alert workflows for user {current_user.id}")
               
            else:
                logger.warning(f"Invalid workflow type received: {workflow_type}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid workflow type: {workflow_type}. Valid types are: {[t.value for t in WorkflowType]}"
                )
           
            # Validate results
            if workflows is None:
                logger.warning(f"Query returned None for user {current_user.id} and type {workflow_type.value}")
                workflows = []
           
            # Log successful retrieval
            logger.info(f"Successfully retrieved {len(workflows)} {workflow_type.value} workflows for user {current_user.id}")
           
            flows = {
            "workflows":   [
                        {
                            "workFlowId": flow.id,
                            "workFlowName": flow.title,
                            "workFlowDescription": flow.description,
                            "steps": flow.steps,
                            "threadId": str(flow.thread.id) if flow.thread else None,
                            "threadName": flow.thread.title if flow.thread else None,
                            "projectId": flow.thread.project.id if flow.thread and flow.thread.project else None,
                            "projectName": flow.thread.project.name if flow.thread and flow.thread.project else None,
                            "workspaceId": flow.thread.project.workspace.id if flow.thread and flow.thread.project and flow.thread.project.workspace else None,
                            "workspaceName": flow.thread.project.workspace.name if flow.thread and flow.thread.project and flow.thread.project.workspace else None,
                            "createdAt": str(flow.created_at)
                        }
                        for flow in workflows] ,
            "total_count": len(workflows),
            "workflow_type": workflow_type.value,
            "user_id": current_user.id,
            "success": True,
            "message": f"Successfully retrieved {len(workflows)} {workflow_type.value} workflows"
        }
            return flows
           
        except HTTPException:
            # Re-raise HTTP exceptions without modification
            raise
           
        except SQLAlchemyError as e:
            # Handle database-specific errors
            error_msg = f"Database error while fetching {workflow_type.value if workflow_type else 'unknown'} workflows for user {getattr(current_user, 'id', 'unknown')}"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"SQLAlchemy traceback: {traceback.format_exc()}")
           
            raise HTTPException(
                status_code=500,
                detail=f"Database error occurred while fetching workflows. Error ID: {id(e)}"
            )
           
        except AttributeError as e:
            # Handle cases where objects might be missing expected attributes
            error_msg = f"Attribute error while fetching workflows"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Attribute error traceback: {traceback.format_exc()}")
           
            # Log context information
            logger.error(f"Workflow type: {workflow_type}")
            logger.error(f"Current user: {current_user}")
            logger.error(f"Database session: {self.db}")
           
            raise HTTPException(
                status_code=500,
                detail="Internal server error: Missing required attributes"
            )
           
        except ValueError as e:
            # Handle value-related errors (e.g., invalid enum values, type conversion issues)
            error_msg = f"Value error while processing workflow request"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Value error traceback: {traceback.format_exc()}")
           
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request parameters: {str(e)}"
            )
           
        except TypeError as e:
            # Handle type-related errors
            error_msg = f"Type error while fetching workflows"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Type error traceback: {traceback.format_exc()}")
           
            # Log parameter types for debugging
            logger.error(f"Parameter types - workflow_type: {type(workflow_type)}, current_user: {type(current_user)}")
           
            raise HTTPException(
                status_code=400,
                detail="Invalid parameter types provided"
            )
           
        except Exception as e:
            # Catch-all for any other unexpected errors
            error_id = id(e)  # Generate unique error ID for tracking
            error_msg = f"Unexpected error while fetching workflows"
           
            logger.error(f"{error_msg} (Error ID: {error_id}): {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
           
            # Log context information for debugging
            logger.error(f"Context - Workflow type: {workflow_type}")
            logger.error(f"User ID: {getattr(current_user, 'id', 'Unknown')}")
            logger.error(f"Database session active: {hasattr(self, 'db') and self.db is not None}")
           
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred while fetching workflows. Please contact support with Error ID: {error_id}"
            )
 
    def remove_workflow_from_editors(self, request: AddWorkflowRequest, current_user):
        """
        Remove workflow from editors with comprehensive error handling and logging
       
        Args:
            request: AddWorkflowRequest containing workflow_id and workflow_type
            current_user: The current authenticated user
           
        Returns:
            Dict with success message and workflow details
           
        Raises:
            HTTPException: For client errors (400, 404, 401) or server errors (500)
        """
        try:
            # Input validation
            if not request:
                logger.warning("Request object is None")
                raise HTTPException(
                    status_code=400,
                    detail="Request data is required"
                )
               
            if not hasattr(request, 'workflow_id') or not request.workflow_id:
                logger.warning("Missing or invalid workflow_id in request")
                raise HTTPException(
                    status_code=400,
                    detail="Workflow ID is required"
                )
               
            if not hasattr(request, 'workflow_type') or not request.workflow_type:
                logger.warning("Missing or invalid workflow_type in request")
                raise HTTPException(
                    status_code=400,
                    detail="Workflow type is required"
                )
               
            if not current_user or not hasattr(current_user, 'id'):
                logger.warning("Invalid or missing current_user")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required - invalid user"
                )
           
            # Log the removal request
            logger.info(f"Attempting to remove workflow {request.workflow_id} from {request.workflow_type.value} for user {current_user.id}")
           
            # Find the workflow by ID and user_id
            workflow = self.db.query(Workflow).filter(
                Workflow.id == request.workflow_id,
                Workflow.user_id == current_user.id
            ).first()
           
            if not workflow:
                logger.warning(f"Workflow not found: ID={request.workflow_id}, User={current_user.id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Workflow with ID {request.workflow_id} not found or you don't have permission to access it"
                )
           
            # Store original state for rollback reference and logging
            original_state = {
                'is_dashboard': workflow.is_dashboard,
                'is_report': workflow.is_report,
                'is_alerts': getattr(workflow, 'is_alerts', getattr(workflow, 'is_alert', None))  # Handle both naming conventions
            }
           
            # Validate that the workflow is currently assigned to the requested type
            current_assignment = False
            if request.workflow_type == WorkflowType.DASHBOARD:
                current_assignment = workflow.is_dashboard
            elif request.workflow_type == WorkflowType.REPORT:
                current_assignment = workflow.is_report
            elif request.workflow_type == WorkflowType.ALERTS:
                current_assignment = getattr(workflow, 'is_alerts', getattr(workflow, 'is_alert', False))
           
            if not current_assignment:
                logger.warning(f"Workflow {request.workflow_id} is not currently assigned to {request.workflow_type.value}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Workflow is not currently assigned to {request.workflow_type.value}"
                )
           
            # Update the appropriate field based on workflow type
            if request.workflow_type == WorkflowType.DASHBOARD:
                workflow.is_dashboard = False
                logger.info(f"Setting is_dashboard=False for workflow {request.workflow_id}")
            elif request.workflow_type == WorkflowType.REPORT:
                workflow.is_report = False
                logger.info(f"Setting is_report=False for workflow {request.workflow_id}")
            elif request.workflow_type == WorkflowType.ALERTS:
                # Handle both possible column names
                if hasattr(workflow, 'is_alerts'):
                    workflow.is_alerts = False
                    logger.info(f"Setting is_alerts=False for workflow {request.workflow_id}")
                elif hasattr(workflow, 'is_alert'):
                    workflow.is_alert = False
                    logger.info(f"Setting is_alert=False for workflow {request.workflow_id}")
                else:
                    logger.error(f"Neither is_alerts nor is_alert column found in workflow model")
                    raise HTTPException(
                        status_code=500,
                        detail="Internal server error: Invalid workflow model structure"
                    )
            else:
                logger.error(f"Invalid workflow type: {request.workflow_type}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid workflow type: {request.workflow_type}. Valid types are: {[t.value for t in WorkflowType]}"
                )
           
            # Save to database
            self.db.commit()
            self.db.refresh(workflow)
           
            logger.info(f"Successfully removed workflow {request.workflow_id} from {request.workflow_type.value}")
           
            return {
                "message": f"Workflow {request.workflow_id} successfully removed from {request.workflow_type.value}",
                "workflow_id": workflow.id,
                "workflow_type": request.workflow_type.value,
                "removed": True,
                "previous_state": original_state
            }
           
        except HTTPException:
            # Re-raise HTTP exceptions without modification
            raise
           
        except SQLAlchemyError as e:
            # Handle database-specific errors
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
           
            error_msg = f"Database error while removing workflow {getattr(request, 'workflow_id', 'unknown')} from {getattr(request, 'workflow_type', 'unknown')}"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"SQLAlchemy traceback: {traceback.format_exc()}")
           
            raise HTTPException(
                status_code=500,
                detail=f"Database error occurred while removing workflow. Error ID: {id(e)}"
            )
           
        except AttributeError as e:
            # Handle cases where workflow object might be None or missing attributes
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
           
            error_msg = f"Attribute error while processing workflow removal"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Attribute error traceback: {traceback.format_exc()}")
           
            # Log context information
            logger.error(f"Request: {request}")
            logger.error(f"Current user: {current_user}")
            logger.error(f"Workflow object: {locals().get('workflow', 'Not found')}")
           
            raise HTTPException(
                status_code=500,
                detail="Internal server error: Invalid workflow data structure"
            )
           
        except ValueError as e:
            # Handle value-related errors (e.g., invalid enum values)
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
           
            error_msg = f"Value error while processing workflow removal"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Value error traceback: {traceback.format_exc()}")
           
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request data: {str(e)}"
            )
           
        except TypeError as e:
            # Handle type-related errors
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
           
            error_msg = f"Type error while processing workflow removal"
            logger.error(f"{error_msg}: {str(e)}")
            logger.error(f"Type error traceback: {traceback.format_exc()}")
           
            # Log parameter types for debugging
            logger.error(f"Parameter types - request: {type(request)}, current_user: {type(current_user)}")
           
            raise HTTPException(
                status_code=400,
                detail="Invalid parameter types provided"
            )
           
        except Exception as e:
            # Catch-all for any other unexpected errors
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction during unexpected error: {rollback_error}")
                logger.error(f"Rollback traceback: {traceback.format_exc()}")
           
            error_id = id(e)  # Generate unique error ID for tracking
            error_msg = f"Unexpected error while removing workflow"
           
            logger.error(f"{error_msg} (Error ID: {error_id}): {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
           
            # Log request details for debugging
            logger.error(f"Request details - Workflow ID: {getattr(request, 'workflow_id', 'Unknown')}")
            logger.error(f"Workflow Type: {getattr(request, 'workflow_type', 'Unknown')}")
            logger.error(f"User ID: {getattr(current_user, 'id', 'Unknown')}")
           
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred while removing workflow. Please contact support with Error ID: {error_id}"
            )