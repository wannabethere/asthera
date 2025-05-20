from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from app.models.thread import Thread, ThreadMessage, Workflow, Note, Timeline, ThreadCollaborator, ThreadConfiguration
from app.schemas.thread import (
    ThreadCreate,
    ThreadMessageCreate,
    WorkflowCreate,
    NoteCreate,
    TimelineCreate,
    WorkflowStep,
    TimelineEvent,
    ThreadCollaboratorCreate,
    ThreadCollaboratorUpdate,
    ThreadConfigurationCreate,
    ThreadConfigurationUpdate
)
from app.models.team import CollaborationRequest
from app.models.user import User
from app.services.authorization import check_project_access
from app.utils.logger import logger
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import json
from app.models.workspace import Project, ProjectAccess

class ThreadService:
    def __init__(self, db: Session):
        self.db = db

    def create_thread(self, thread_data: ThreadCreate) -> Thread:
        """Create a new thread"""
        try:
            thread = Thread(
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
        return self.db.query(Thread).filter(Thread.id == thread_id).first()

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

    def create_workflow(self, thread_id: UUID, user_id: UUID, workflow_data: WorkflowCreate) -> Workflow:
        """Create a new workflow in a thread"""
        workflow = Workflow(
            thread_id=thread_id,
            user_id=user_id,
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
        if workflow:
            current_steps = workflow.steps or []
            current_steps.append(step.dict())
            workflow.steps = current_steps
            self.db.commit()
            self.db.refresh(workflow)
        return workflow

    def create_note(self, thread_id: UUID, note_data: NoteCreate) -> Note:
        """Create a new note in a thread"""
        # Get the highest sortorder value for existing notes
        max_sortorder = self.db.query(Note).filter(
            Note.thread_id == thread_id
        ).order_by(Note.sortorder.desc()).first()
        
        new_sortorder = (max_sortorder.sortorder + 1) if max_sortorder else 0
        
        note = Note(
            thread_id=thread_id,
            user_id=note_data.user_id,
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
        project_ids = set()
        DEFAULT_PROJECT_ID = UUID('00000000-0000-0000-0000-000000000003')
        project_ids.add(DEFAULT_PROJECT_ID)

        # If specific project_id is provided, check access and add it
        if project_id:
            if check_project_access(self.db, str(project_id), str(user.id)):
                project_ids.add(project_id)
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

        # Get all projects the user has access to
        accessible_projects = self.db.query(Project).join(
            ProjectAccess, Project.id == ProjectAccess.project_id
        ).filter(ProjectAccess.user_id == str(user.id)).all()
        for project in accessible_projects:
            project_ids.add(project.id)

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
        if not check_project_access(self.db, str(thread.project_id), str(user.id)):
            raise PermissionError("Not authorized to access this thread")
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
        note = self.create_note(thread_id, note_data)
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

    def search_collaborators(self, thread_id: UUID, offset: int = 0, limit: int = 20) -> (List[User], bool):
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