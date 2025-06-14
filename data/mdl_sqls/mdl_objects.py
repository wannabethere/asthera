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
    status = Column(String(20), default='active', nullable=False)
    
    # Versioning fields
    major_version = Column(Integer, default=1, nullable=False)
    minor_version = Column(Integer, default=0, nullable=False)
    patch_version = Column(Integer, default=0, nullable=False)
    last_modified_by = Column(String(100))
    last_modified_entity = Column(String(100))
    last_modified_entity_id = Column(UUID(as_uuid=True))
    version_locked = Column(Boolean, default=False, nullable=False)
    metadata = Column(JSONB)
    
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
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name='check_status'),
        Index('idx_projects_status', 'status'),
        Index('idx_projects_version', 'major_version', 'minor_version', 'patch_version'),
        Index('idx_projects_version_locked', 'version_locked'),
    )
    
    @hybrid_property
    def version_string(self) -> str:
        """Generate version string from major.minor.patch"""
        return f"{self.major_version}.{self.minor_version}.{self.patch_version}"
    
    def increment_version(self, change_type: str, entity_type: str, entity_id: uuid.UUID, 
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
    
    def lock_version(self, locked: bool = True):
        """Lock or unlock project version"""
        if locked and self.version_locked:
            raise ValueError(f"Project {self.project_id} is already version locked")
        self.version_locked = locked
    
    def __repr__(self):
        return f"<Project(id='{self.project_id}', name='{self.display_name}', version='{self.version_string}')>"


class ProjectVersionHistory(Base, TimestampMixin):
    """Track all project version changes"""
    __tablename__ = 'project_version_history'
    
    version_history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    old_version = Column(String(20))
    new_version = Column(String(20))
    change_type = Column(String(20), nullable=False)
    triggered_by_entity = Column(String(100), nullable=False)
    triggered_by_entity_id = Column(UUID(as_uuid=True))
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
    
    dataset_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    metadata = Column(JSONB)
    
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
    
    table_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey('datasets.dataset_id', ondelete='CASCADE'))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    mdl_file = Column(String(200))
    ddl_file = Column(String(200))
    table_type = Column(String(20), default='table', nullable=False)
    metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="tables")
    dataset = relationship("Dataset", back_populates="tables")
    columns = relationship("Column", back_populates="table", cascade="all, delete-orphan")
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


class Column(Base, TimestampMixin, EntityVersionMixin):
    """Table columns with comprehensive metadata"""
    __tablename__ = 'columns'
    
    column_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(UUID(as_uuid=True), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
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
    metadata = Column(JSONB)
    
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
    """Project-level reusable functions"""
    __tablename__ = 'sql_functions'
    
    function_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
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
        UniqueConstraint('project_id', 'name', name='uq_sql_functions_project_name'),
    )


class CalculatedColumn(Base, TimestampMixin, EntityVersionMixin):
    """Special columns with associated functions"""
    __tablename__ = 'calculated_columns'
    
    calculated_column_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    column_id = Column(UUID(as_uuid=True), ForeignKey('columns.column_id', ondelete='CASCADE'), nullable=False)
    calculation_sql = Column(Text, nullable=False)
    function_id = Column(UUID(as_uuid=True), ForeignKey('sql_functions.function_id'))
    dependencies = Column(JSONB)  # Array of column/table dependencies
    
    # Relationships
    column = relationship("Column", back_populates="calculated_column")
    function = relationship("SQLFunction", back_populates="calculated_columns")


class Metric(Base, TimestampMixin, EntityVersionMixin):
    """Table-level metrics and KPIs"""
    __tablename__ = 'metrics'
    
    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(UUID(as_uuid=True), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    metric_sql = Column(Text, nullable=False)
    metric_type = Column(String(50))
    aggregation_type = Column(String(50))
    format_string = Column(String(50))
    metadata = Column(JSONB)
    
    # Relationships
    table = relationship("Table", back_populates="metrics")
    
    __table_args__ = (
        UniqueConstraint('table_id', 'name', name='uq_metrics_table_name'),
    )


class View(Base, TimestampMixin, EntityVersionMixin):
    """Table views and perspectives"""
    __tablename__ = 'views'
    
    view_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(UUID(as_uuid=True), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    view_sql = Column(Text, nullable=False)
    view_type = Column(String(50))
    metadata = Column(JSONB)
    
    # Relationships
    table = relationship("Table", back_populates="views")
    
    __table_args__ = (
        UniqueConstraint('table_id', 'name', name='uq_views_table_name'),
    )


class Relationship(Base, TimestampMixin, EntityVersionMixin):
    """Define relationships between tables/datasets"""
    __tablename__ = 'relationships'
    
    relationship_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100))
    relationship_type = Column(String(50), nullable=False)
    from_table_id = Column(UUID(as_uuid=True), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    to_table_id = Column(UUID(as_uuid=True), ForeignKey('tables.table_id', ondelete='CASCADE'), nullable=False)
    from_column_id = Column(UUID(as_uuid=True), ForeignKey('columns.column_id'))
    to_column_id = Column(UUID(as_uuid=True), ForeignKey('columns.column_id'))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="relationships")
    from_table = relationship("Table", foreign_keys=[from_table_id], back_populates="from_relationships")
    to_table = relationship("Table", foreign_keys=[to_table_id], back_populates="to_relationships")
    from_column = relationship("Column", foreign_keys=[from_column_id], back_populates="from_relationships")
    to_column = relationship("Column", foreign_keys=[to_column_id], back_populates="to_relationships")
    
    __table_args__ = (
        Index('idx_relationships_project_id', 'project_id'),
        Index('idx_relationships_from_table', 'from_table_id'),
        Index('idx_relationships_to_table', 'to_table_id'),
    )


class Instruction(Base, TimestampMixin, EntityVersionMixin):
    """Each instruction item as a row (from instructions.json)"""
    __tablename__ = 'instructions'
    
    instruction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    question = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    chain_of_thought = Column(Text)
    metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="instructions")
    
    __table_args__ = (
        Index('idx_instructions_project_id', 'project_id'),
    )


class Example(Base, TimestampMixin, EntityVersionMixin):
    """Each SQL pair item as a row (from sql_pairs.json)"""
    __tablename__ = 'examples'
    
    example_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    question = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    context = Column(Text)
    document_reference = Column(String(200))
    instructions = Column(Text)
    categories = Column(JSONB)  # Array of category strings
    samples = Column(JSONB)  # Array of sample data
    metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="examples")
    
    __table_args__ = (
        Index('idx_examples_project_id', 'project_id'),
    )


class KnowledgeBase(Base, TimestampMixin, EntityVersionMixin):
    """Project knowledge base entries"""
    __tablename__ = 'knowledge_base'
    
    kb_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    file_path = Column(String(500))
    content_type = Column(String(50))
    content = Column(Text)
    metadata = Column(JSONB)
    
    # Relationships
    project = relationship("Project", back_populates="knowledge_base")
    
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_knowledge_base_project_name'),
        Index('idx_knowledge_base_project_id', 'project_id'),
    )


class ProjectHistory(Base, TimestampMixin):
    """Track changes and versions"""
    __tablename__ = 'project_histories'
    
    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    table_id = Column(UUID(as_uuid=True), ForeignKey('tables.table_id'))
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True))
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


# ============================================================================
# UTILITY CLASSES AND MANAGERS
# ============================================================================

class ProjectManager:
    """Utility class for project management operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_project(self, project_id: str, display_name: str, description: str = None, 
                      created_by: str = 'system') -> Project:
        """Create a new project"""
        project = Project(
            project_id=project_id,
            display_name=display_name,
            description=description,
            created_by=created_by,
            last_modified_by=created_by
        )
        self.session.add(project)
        self.session.commit()
        return project
    
    def lock_project_version(self, project_id: str, locked: bool = True, 
                           modified_by: str = 'system') -> bool:
        """Lock or unlock project version"""
        project = self.session.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            return False
        
        project.lock_version(locked)
        project.last_modified_by = modified_by
        self.session.commit()
        return True
    
    def manual_version_increment(self, project_id: str, change_type: str, 
                               modified_by: str, description: str) -> Optional[str]:
        """Manually increment project version"""
        project = self.session.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            return None
        
        old_version = project.version_string
        new_version = project.increment_version(
            change_type=change_type,
            entity_type='manual',
            entity_id=None,
            modified_by=modified_by
        )
        
        # Create version history
        version_history = ProjectVersionHistory(
            project_id=project_id,
            old_version=old_version,
            new_version=new_version,
            change_type=change_type,
            triggered_by_entity='manual',
            triggered_by_user=modified_by,
            change_description=description
        )
        self.session.add(version_history)
        self.session.commit()
        
        return new_version
    
    def get_project_summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive project summary"""
        project = self.session.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            return None
        
        return {
            'project_id': project.project_id,
            'display_name': project.display_name,
            'current_version': project.version_string,
            'version_locked': project.version_locked,
            'last_modified_by': project.last_modified_by,
            'last_modified_entity': project.last_modified_entity,
            'status': project.status,
            'total_datasets': len(project.datasets),
            'total_tables': len(project.tables),
            'total_instructions': len(project.instructions),
            'total_examples': len(project.examples),
            'total_knowledge_base': len(project.knowledge_base),
            'version_changes': len(project.version_history),
            'created_at': project.created_at,
            'updated_at': project.updated_at
        }


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