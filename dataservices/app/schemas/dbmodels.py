"""
SQLAlchemy Models for Project Management System with Comprehensive Versioning
Supports automatic project version updates when any related entity is modified
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey,
    CheckConstraint, UniqueConstraint, Index, event
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, validates
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property

Base = declarative_base()


class TimestampMixin:
    """Mixin for timestamp fields"""
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class EntityVersionMixin:
    """Mixin for entity versioning"""
    entity_version = Column(Integer, default=1, nullable=False)
    modified_by = Column(String(100))


class Project(Base, TimestampMixin):
    """Main project entity with semantic versioning"""
    __tablename__ = 'projects'
    
    project_id = Column(String(50), primary_key=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    created_by = Column(String(100))
    # Enhanced status management for workflow
    status = Column(String(20), default='draft', nullable=False)
    """
    Status values:
    - 'draft': Initial creation, adding tables and columns
    - 'draft_ready': Tables completed, ready for metrics/views
    - 'review': Under review before publishing  
    - 'active': Published and live
    - 'inactive': Temporarily disabled
    - 'archived': Permanently archived
    """

    
    # Versioning fields
    major_version = Column(Integer, default=1, nullable=False)
    minor_version = Column(Integer, default=0, nullable=False)
    patch_version = Column(Integer, default=0, nullable=False)
    last_modified_by = Column(String(100))
    last_modified_entity = Column(String(100))
    last_modified_entity_id = Column(String(36))
    version_locked = Column(Boolean, default=False, nullable=False)
    json_metadata = Column(JSONB)
    
    # Workflow tracking fields
    draft_completed_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    
    # Relationships
    datasets = relationship("Dataset", back_populates="project", cascade="all, delete-orphan")
    tables = relationship("Table", back_populates="project", cascade="all, delete-orphan")
    sql_functions = relationship("SQLFunction", back_populates="project", cascade="all, delete-orphan")
    relationships = relationship("Relationship", back_populates="project", cascade="all, delete-orphan")
    instructions = relationship("Instruction", back_populates="project", cascade="all, delete-orphan")
    examples = relationship("Example", back_populates="project", cascade="all, delete-orphan")
    knowledge_base = relationship("KnowledgeBase", back_populates="project", cascade="all, delete-orphan")
    version_history = relationship("ProjectVersionHistory", back_populates="project", cascade="all, delete-orphan")
    project_histories = relationship("ProjectHistory", back_populates="project", cascade="all, delete-orphan")
    
   # Enhanced constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'draft_ready', 'review', 'active', 'inactive', 'archived')", 
            name='check_status'
        ),
        Index('idx_projects_status', 'status'),
        Index('idx_projects_version', 'major_version', 'minor_version', 'patch_version'),
        Index('idx_projects_version_locked', 'version_locked'),
        Index('idx_projects_created_at', 'created_at'),
    )
    @hybrid_property
    def version_string(self) -> str:
        """Generate version string from major.minor.patch"""
        return f"{self.major_version}.{self.minor_version}.{self.patch_version}"
    
    @hybrid_property
    def is_draft(self) -> bool:
        """Check if project is in any draft state"""
        return self.status in ['draft', 'draft_ready']
    
    @hybrid_property
    def is_published(self) -> bool:
        """Check if project is published"""
        return self.status == 'active'
    
    @hybrid_property
    def can_add_tables(self) -> bool:
        """Check if tables can be added"""
        return self.status == 'draft'
    
    @hybrid_property
    def can_add_metrics(self) -> bool:
        """Check if metrics/views can be added"""
        return self.status in ['draft_ready', 'review']
    
    @hybrid_property
    def table_count(self) -> int:
        """Get count of tables"""
        return len(self.tables) if self.tables else 0
    
    def transition_to_draft_ready(self, user: str = 'system') -> bool:
        """Transition from draft to draft_ready"""
        if self.status != 'draft':
            raise ValueError(f"Cannot transition to draft_ready from {self.status}")
        
        if self.table_count == 0:
            raise ValueError("Project must have at least one table")
        
        self.status = 'draft_ready'
        self.draft_completed_at = func.now()
        self.last_modified_by = user
        return True
    
    def transition_to_review(self, user: str = 'system') -> bool:
        """Transition to review status"""
        if self.status != 'draft_ready':
            raise ValueError(f"Cannot transition to review from {self.status}")
        
        self.status = 'review'
        self.last_modified_by = user
        return True
    
    def publish(self, user: str = 'system') -> bool:
        """Publish the project"""
        if self.status not in ['draft_ready', 'review']:
            raise ValueError(f"Cannot publish from {self.status}")
        
        self.status = 'active'
        self.published_at = func.now()
        self.version_locked = False  # Unlock for future modifications
        self.last_modified_by = user
        return True
    
    def archive(self, user: str = 'system') -> bool:
        """Archive the project"""
        self.status = 'archived'
        self.last_modified_by = user
        return True
    
    def increment_version(self, change_type: str, entity_type: str, entity_id: str, 
                         modified_by: str, description: Optional[str] = None) -> str:
        """Increment project version based on change type"""
        old_version = self.version_string
        
        if change_type == 'major':
            self.major_version += 1
            self.minor_version = 0
            self.patch_version = 0
        elif change_type == 'minor':
            self.minor_version += 1
            self.patch_version = 0
        elif change_type == 'patch':
            self.patch_version += 1
        else:
            raise ValueError(f"Invalid change_type: {change_type}. Must be major, minor, or patch")
        
        new_version = self.version_string
        self.last_modified_by = modified_by
        self.last_modified_entity = entity_type
        self.last_modified_entity_id = entity_id
        self.updated_at = func.now()
        
        return new_version
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get comprehensive workflow status"""
        return {
            'status': self.status,
            'is_draft': self.is_draft,
            'is_published': self.is_published,
            'can_add_tables': self.can_add_tables,
            'can_add_metrics': self.can_add_metrics,
            'table_count': self.table_count,
            'version': self.version_string,
            'created_at': self.created_at,
            'draft_completed_at': self.draft_completed_at,
            'published_at': self.published_at,
            'last_modified_by': self.last_modified_by
        }
    
    def __repr__(self):
        return f"<Project(id='{self.project_id}', name='{self.display_name}', status='{self.status}', version='{self.version_string}')>"


class ProjectVersionHistory(Base, TimestampMixin):
    """Track all project version changes"""
    __tablename__ = 'project_version_history'
    
    version_history_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    old_version = Column(String(20))
    new_version = Column(String(20))
    change_type = Column(String(20), nullable=False)
    triggered_by_entity = Column(String(100), nullable=False)
    triggered_by_entity_id = Column(String(36))
    triggered_by_user = Column(String(100))
    change_description = Column(Text)
    
    # Relationships
    project = relationship("Project", back_populates="version_history")
    
    __table_args__ = (
        Index('idx_project_version_history_project_id', 'project_id'),
        Index('idx_project_version_history_created_at', 'created_at'),
    )


class Dataset(Base, TimestampMixin, EntityVersionMixin):
    """Collections of tables within a project"""
    __tablename__ = 'datasets'
    
    dataset_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    json_metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="datasets")
    tables = relationship("Table", back_populates="dataset", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_datasets_project_name'),
        Index('idx_datasets_project_id', 'project_id'),
        Index('idx_datasets_entity_version', 'entity_version'),
    )


class Table(Base, TimestampMixin, EntityVersionMixin):
    """Individual data tables with descriptions"""
    __tablename__ = 'tables'
    
    table_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String(36), ForeignKey('datasets.dataset_id', ondelete='CASCADE'))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    mdl_file = Column(String(200))
    ddl_file = Column(String(200))
    table_type = Column(String(20), default='table', nullable=False)
    json_metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="tables")
    dataset = relationship("Dataset", back_populates="tables")
    columns = relationship("SQLColumn", back_populates="table", cascade="all, delete-orphan")
    metrics = relationship("Metric", back_populates="table", cascade="all, delete-orphan")
    views = relationship("View", back_populates="table", cascade="all, delete-orphan")
    from_relationships = relationship("Relationship", foreign_keys="[Relationship.from_table_id]", back_populates="from_table")
    to_relationships = relationship("Relationship", foreign_keys="[Relationship.to_table_id]", back_populates="to_table")
    
    __table_args__ = (
        CheckConstraint("table_type IN ('table', 'view', 'materialized_view')", name='check_table_type'),
        UniqueConstraint('project_id', 'name', name='uq_tables_project_name'),
        Index('idx_tables_project_id', 'project_id'),
        Index('idx_tables_dataset_id', 'dataset_id'),
        Index('idx_tables_entity_version', 'entity_version'),
    )


class SQLColumn(Base, TimestampMixin, EntityVersionMixin):
    """Table columns with comprehensive metadata"""
    __tablename__ = 'columns'
    
    column_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_id = Column(String(36), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    column_type = Column(String(20), default='column', nullable=False)
    data_type = Column(String(50))
    usage_type = Column(String(50))
    is_nullable = Column(Boolean, default=True)
    is_primary_key = Column(Boolean, default=False)
    is_foreign_key = Column(Boolean, default=False)
    default_value = Column(Text)
    ordinal_position = Column(Integer)
    json_metadata = Column(JSONB)
    
    # Relationships
    table = relationship("Table", back_populates="columns")
    calculated_column = relationship("CalculatedColumn", back_populates="column", uselist=False, cascade="all, delete-orphan")
    from_relationships = relationship("Relationship", foreign_keys="[Relationship.from_column_id]", back_populates="from_column")
    to_relationships = relationship("Relationship", foreign_keys="[Relationship.to_column_id]", back_populates="to_column")
    
    __table_args__ = (
        CheckConstraint("column_type IN ('column', 'calculated_column')", name='check_column_type'),
        UniqueConstraint('table_id', 'name', name='uq_columns_table_name'),
        Index('idx_columns_table_id', 'table_id'),
        Index('idx_columns_type', 'column_type'),
        Index('idx_columns_entity_version', 'entity_version'),
    )


class SQLFunction(Base, TimestampMixin, EntityVersionMixin):
    """Project-level reusable functions with optional project association"""
    __tablename__ = 'sql_functions'
    
    function_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    function_sql = Column(Text, nullable=False)
    return_type = Column(String(50))
    parameters = Column(JSONB)  # Array of parameter definitions
    
    # Relationships
    project = relationship("Project", back_populates="sql_functions")
    calculated_columns = relationship("CalculatedColumn", back_populates="function")
    
    __table_args__ = (
        # Partial unique constraint - only enforce uniqueness when project_id is not null
        # This allows global functions (project_id = null) to have the same name as project-specific functions
        UniqueConstraint('project_id', 'name', name='uq_sql_functions_project_name', deferrable=True),
        Index('idx_sql_functions_project_id', 'project_id'),
        Index('idx_sql_functions_name', 'name'),
    )


class CalculatedColumn(Base, TimestampMixin, EntityVersionMixin):
    """Special columns with associated functions"""
    __tablename__ = 'calculated_columns'
    
    calculated_column_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    column_id = Column(String(36), ForeignKey('columns.column_id', ondelete='CASCADE'), nullable=False)
    calculation_sql = Column(Text, nullable=False)
    function_id = Column(String(36), ForeignKey('sql_functions.function_id'))
    dependencies = Column(JSONB)  # Array of column/table dependencies
    
    # Relationships
    column = relationship("SQLColumn", back_populates="calculated_column")
    function = relationship("SQLFunction", back_populates="calculated_columns")


class Metric(Base, TimestampMixin, EntityVersionMixin):
    """Table-level metrics and KPIs"""
    __tablename__ = 'metrics'
    
    metric_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_id = Column(String(36), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    metric_sql = Column(Text, nullable=False)
    metric_type = Column(String(50))
    aggregation_type = Column(String(50))
    format_string = Column(String(50))
    json_metadata = Column(JSONB)
    
    # Relationships
    table = relationship("Table", back_populates="metrics")
    
    __table_args__ = (
        UniqueConstraint('table_id', 'name', name='uq_metrics_table_name'),
    )


class View(Base, TimestampMixin, EntityVersionMixin):
    """Table views and perspectives"""
    __tablename__ = 'views'
    
    view_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_id = Column(String(36), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    view_sql = Column(Text, nullable=False)
    view_type = Column(String(50))
    json_metadata = Column(JSONB)
    
    # Relationships
    table = relationship("Table", back_populates="views")
    
    __table_args__ = (
        UniqueConstraint('table_id', 'name', name='uq_views_table_name'),
    )


class Relationship(Base, TimestampMixin, EntityVersionMixin):
    """Define relationships between tables/datasets"""
    __tablename__ = 'relationships'
    
    relationship_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100))
    relationship_type = Column(String(50), nullable=False)
    from_table_id = Column(String(36), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    to_table_id = Column(String(36), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    from_column_id = Column(String(36), ForeignKey('columns.column_id'))
    to_column_id = Column(String(36), ForeignKey('columns.column_id'))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    json_metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="relationships")
    from_table = relationship("Table", foreign_keys=[from_table_id], back_populates="from_relationships")
    to_table = relationship("Table", foreign_keys=[to_table_id], back_populates="to_relationships")
    from_column = relationship("SQLColumn", foreign_keys=[from_column_id], back_populates="from_relationships")
    to_column = relationship("SQLColumn", foreign_keys=[to_column_id], back_populates="to_relationships")
    
    __table_args__ = (
        Index('idx_relationships_project_id', 'project_id'),
        Index('idx_relationships_from_table', 'from_table_id'),
        Index('idx_relationships_to_table', 'to_table_id'),
    )


class Instruction(Base, TimestampMixin, EntityVersionMixin):
    """Each instruction item as a row (from instructions.json)"""
    __tablename__ = 'instructions'
    
    instruction_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    instruction_type = Column(String(20), nullable=False, default='sql_query')  # 'sql_query' or 'instructions'
    question = Column(Text, nullable=False)
    instructions = Column(Text)  # Now nullable
    sql_query = Column(Text)  # Now nullable
    chain_of_thought = Column(Text)
    json_metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="instructions")
    
    __table_args__ = (
        Index('idx_instructions_project_id', 'project_id'),
        CheckConstraint(
            "(sql_query IS NOT NULL AND instruction_type = 'sql_query') OR (instructions IS NOT NULL AND instruction_type = 'instructions')",
            name='check_instruction_type_content'
        ),
    )


class Example(Base, TimestampMixin, EntityVersionMixin):
    """Each SQL pair item as a row (from sql_pairs.json)"""
    __tablename__ = 'examples'
    
    example_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    definition_type = Column(String(50), nullable=False, default='sql_pair')  # 'metric', 'view', 'calculated_column', 'sql_pair', 'instruction'
    name = Column(String(100), nullable=False)  # Add name field to match UserExample
    question = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    context = Column(Text)
    document_reference = Column(String(200))
    instructions = Column(Text)
    categories = Column(JSONB)  # Array of category strings
    samples = Column(JSONB)  # Array of sample data
    additional_context = Column(JSONB)  # Add additional_context field to match UserExample
    user_id = Column(String(100), default='system')  # Add user_id field to match UserExample
    json_metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="examples")
    
    __table_args__ = (
        CheckConstraint(
            "definition_type IN ('metric', 'view', 'calculated_column', 'sql_pair', 'instruction')", 
            name='check_definition_type'
        ),
        Index('idx_examples_project_id', 'project_id'),
        Index('idx_examples_definition_type', 'definition_type'),
    )


class KnowledgeBase(Base, TimestampMixin, EntityVersionMixin):
    """Project knowledge base entries"""
    __tablename__ = 'knowledge_base'
    
    kb_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    file_path = Column(String(500))
    content_type = Column(String(50))
    content = Column(Text)
    json_metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="knowledge_base")
    
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_knowledge_base_project_name'),
        Index('idx_knowledge_base_project_id', 'project_id'),
    )

class ProjectHistory(Base, TimestampMixin):
    """Track changes and versions"""
    __tablename__ = 'project_histories'
    
    history_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    table_id = Column(String(36), ForeignKey('tables.table_id'))
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36))
    action = Column(String(20), nullable=False)
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    old_entity_version = Column(Integer)
    new_entity_version = Column(Integer)
    changed_by = Column(String(100))
    change_description = Column(Text)
    project_version_before = Column(String(20))
    project_version_after = Column(String(20))
    
    # Relationships
    project = relationship("Project", back_populates="project_histories")
    table = relationship("Table")
    
    __table_args__ = (
        Index('idx_project_histories_project_id', 'project_id'),
        Index('idx_project_histories_entity', 'entity_type', 'entity_id'),
        Index('idx_project_histories_changed_at', 'created_at'),
    )


# ============================================================================
# UTILITY FUNCTIONS AND EVENT HANDLERS
# ============================================================================

def determine_change_type(entity_type: str, action: str, old_values: Optional[Dict] = None, 
                         new_values: Optional[Dict] = None) -> str:
    """Determine change type based on entity and modification"""
    # Major version changes (breaking changes)
    if (action == 'delete' or 
        entity_type in ['tables', 'columns', 'relationships'] or
        (entity_type == 'sql_functions' and action in ['update', 'delete']) or
        (entity_type == 'calculated_columns' and action in ['update', 'delete'])):
        return 'major'
    
    # Minor version changes (new features, non-breaking changes)
    if (action == 'create' or
        entity_type in ['metrics', 'views', 'instructions', 'examples', 'knowledge_base']):
        return 'minor'
    
    # Patch version changes (updates, fixes)
    if action == 'update':
        return 'patch'
    
    # Default to patch for any other changes
    return 'patch'


def update_project_version(session: Session, entity: Any, action: str):
    """Update project version when any entity is modified"""
    # Skip if it's a Project entity itself to avoid recursion
    if isinstance(entity, Project):
        return
    
    # Get project_id based on entity type
    project_id = None
    entity_type = entity.__class__.__name__.lower()
    entity_id = None
    modified_by = getattr(entity, 'modified_by', 'system')
    
    if hasattr(entity, 'project_id'):
        project_id = entity.project_id
        entity_id = getattr(entity, f"{entity_type}_id", None)
    elif hasattr(entity, 'table_id'):
        # For entities related through table
        table = session.query(Table).filter(Table.table_id == entity.table_id).first()
        if table:
            project_id = table.project_id
            entity_id = getattr(entity, f"{entity_type}_id", None)
    elif hasattr(entity, 'column_id'):
        # For calculated_columns
        column = session.query(Column).filter(Column.column_id == entity.column_id).first()
        if column and column.table:
            project_id = column.table.project_id
            entity_id = getattr(entity, f"{entity_type}_id", None)
    
    # Skip version update for global entities (no project_id) like global SQL functions
    if not project_id:
        return
    
    # Get the project
    project = session.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        return
    
    # Check if project is version locked
    if project.version_locked:
        raise ValueError(f"Project {project_id} is version locked. Cannot modify.")
    
    # Determine change type and update project version
    change_type = determine_change_type(entity_type, action)
    old_version = project.version_string
    
    new_version = project.increment_version(
        change_type=change_type,
        entity_type=entity_type,
        entity_id=entity_id,
        modified_by=modified_by
    )
    
    # Create version history record
    version_history = ProjectVersionHistory(
        project_id=project_id,
        old_version=old_version,
        new_version=new_version,
        change_type=change_type,
        triggered_by_entity=entity_type,
        triggered_by_entity_id=entity_id,
        triggered_by_user=modified_by,
        change_description=f"Triggered by {action} on {entity_type}"
    )
    session.add(version_history)


# Event listeners for automatic version updates
@event.listens_for(Session, 'before_flush')
def before_flush(session, flush_context, instances):
    """Handle version updates before flush"""
    # Track new, dirty, and deleted objects
    for obj in session.new:
        if hasattr(obj, '__tablename__') and obj.__tablename__ != 'projects':
            update_project_version(session, obj, 'create')
    
    for obj in session.dirty:
        if hasattr(obj, '__tablename__') and obj.__tablename__ != 'projects':
            update_project_version(session, obj, 'update')
    
    for obj in session.deleted:
        if hasattr(obj, '__tablename__') and obj.__tablename__ != 'projects':
            update_project_version(session, obj, 'delete')



# Additional helper models for workflow tracking

class WorkflowLog(Base, TimestampMixin):
    """Track workflow transitions and actions"""
    __tablename__ = 'workflow_logs'
    
    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    action = Column(String(50), nullable=False)  # 'created', 'table_added', 'draft_ready', 'published', etc.
    from_status = Column(String(20))
    to_status = Column(String(20))
    user_id = Column(String(100))
    notes = Column(Text)
    json_metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project")
    
    __table_args__ = (
        Index('idx_workflow_logs_project_id', 'project_id'),
        Index('idx_workflow_logs_action', 'action'),
        Index('idx_workflow_logs_created_at', 'created_at'),
    )

# Event handlers for workflow logging
@event.listens_for(Project.status, 'set')
def log_status_change(target, value, old_value, initiator):
    """Log status changes"""
    if old_value != value and old_value is not None:
        # This would need to be implemented with session context
        print(f"Status changed from {old_value} to {value} for project {target.project_id}")

# Enhanced utility functions

def validate_project_transition(project: Project, new_status: str) -> bool:
    """Validate if a status transition is allowed"""
    valid_transitions = {
        'draft': ['draft_ready', 'archived'],
        'draft_ready': ['review', 'active', 'archived'],
        'review': ['active', 'draft_ready', 'archived'],
        'active': ['inactive', 'archived'],
        'inactive': ['active', 'archived'],
        'archived': []  # Cannot transition from archived
    }
    
    return new_status in valid_transitions.get(project.status, [])

def get_project_completion_score(project: Project) -> float:
    """Calculate project completion score (0-100)"""
    score = 0.0
    
    # Basic structure (40 points)
    if project.table_count > 0:
        score += 20
    if project.table_count >= 2:
        score += 10
    if project.description:
        score += 10
    
    # Tables with columns (30 points)
    if project.tables:
        tables_with_columns = sum(1 for table in project.tables if table.column_count > 0)
        score += (tables_with_columns / len(project.tables)) * 30
    
    # Semantic descriptions (20 points)
    if project.tables:
        tables_with_semantic = sum(1 for table in project.tables if table.has_semantic_description)
        score += (tables_with_semantic / len(project.tables)) * 20
    
    # Metrics and views (10 points)
    total_metrics = sum(len(table.metrics) for table in project.tables if table.metrics)
    total_views = sum(len(table.views) for table in project.tables if table.views)
    if total_metrics > 0 or total_views > 0:
        score += 10
    
    return min(score, 100.0)



class ProjectJSONStore(Base, TimestampMixin):
    """Store project JSON data with ChromaDB integration"""
    __tablename__ = 'project_json_store'
    
    store_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    
    # ChromaDB document ID for the stored JSON
    chroma_document_id = Column(String(100), nullable=False, unique=True)
    
    # JSON data type and content
    json_type = Column(String(50), nullable=False)  # 'tables', 'metrics', 'views', 'calculated_columns', 'enums', 'project'
    json_content = Column(JSONB, nullable=False)
    
    # Metadata
    version = Column(String(20), default='1.0.0')
    is_active = Column(Boolean, default=True)
    last_updated_by = Column(String(100))
    update_reason = Column(Text)
    
    # Relationships
    project = relationship("Project")
    
    __table_args__ = (
        Index('idx_project_json_store_project_id', 'project_id'),
        Index('idx_project_json_store_type', 'json_type'),
        Index('idx_project_json_store_chroma_id', 'chroma_document_id'),
        Index('idx_project_json_store_active', 'is_active'),
        UniqueConstraint('project_id', 'json_type', name='uq_project_json_type'),
    )
    
    def __repr__(self):
        return f"<ProjectJSONStore(id='{self.store_id}', project='{self.project_id}', type='{self.json_type}', chroma_id='{self.chroma_document_id}')>"
    

# Example usage and testing
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Example database connection (replace with your actual connection string)
    # engine = create_engine('postgresql://user:password@localhost/project_db')
    # Base.metadata.create_all(engine)
    # Session = sessionmaker(bind=engine)
    # session = Session()
    
    # # Example usage
    # project_manager = ProjectManager(session)
    # 
    # # Create a project
    # project = project_manager.create_project(
    #     project_id='test_project',
    #     display_name='Test Project',
    #     description='A test project for demonstration',
    #     created_by='admin'
    # )
    # 
    # print(f"Created project: {project.version_string}")
    # 
    # # Add a table (this will automatically increment version)
    # table = Table(
    #     project_id='test_project',
    #     name='test_table',
    #     display_name='Test Table',
    #     modified_by='admin'
    # )
    # session.add(table)
    # session.commit()
    # 
    # # Check updated version
    # session.refresh(project)
    # print(f"After adding table: {project.version_string}")
    # 
    # # Get project summary
    # summary = project_manager.get_project_summary('test_project')
    # print(f"Project summary: {summary}")
    
    pass