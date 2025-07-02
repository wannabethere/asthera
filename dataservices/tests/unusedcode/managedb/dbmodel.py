import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    event,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from app.service.database import Base
from sqlalchemy.orm import relationship, Session, validates
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property


class TimestampMixin:
    """Mixin for timestamp fields"""

    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )


class EntityVersionMixin:
    """Mixin for entity versioning"""

    entity_version = Column(Integer, default=1, nullable=False)
    modified_by = Column(String(100))


class Project(Base, TimestampMixin):
    """Main project entity with semantic versioning"""

    __tablename__ = "projects"

    project_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    created_by = Column(String(100))
    status = Column(String(20), default="active", nullable=False)

    # Versioning fields
    major_version = Column(Integer, default=1, nullable=False)
    minor_version = Column(Integer, default=0, nullable=False)
    patch_version = Column(Integer, default=0, nullable=False)
    last_modified_by = Column(String(100))
    last_modified_entity = Column(String(100))
    last_modified_entity_id = Column(UUID(as_uuid=True))
    version_locked = Column(Boolean, default=False, nullable=False)
    project_metadata = Column(JSONB)

    # Relationships
    datasets = relationship(
        "Dataset", back_populates="project", cascade="all, delete-orphan"
    )
    tables = relationship(
        "Table", back_populates="project", cascade="all, delete-orphan"
    )
    sql_functions = relationship(
        "SQLFunction", back_populates="project", cascade="all, delete-orphan"
    )
    relationships = relationship(
        "Relationship", back_populates="project", cascade="all, delete-orphan"
    )
    instructions = relationship(
        "Instruction", back_populates="project", cascade="all, delete-orphan"
    )
    examples = relationship(
        "Example", back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_base = relationship(
        "KnowledgeBase", back_populates="project", cascade="all, delete-orphan"
    )
    version_history = relationship(
        "ProjectVersionHistory", back_populates="project", cascade="all, delete-orphan"
    )
    project_histories = relationship(
        "ProjectHistory", back_populates="project", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')", name="check_status"
        ),
        Index("idx_projects_status", "status"),
        Index(
            "idx_projects_version", "major_version", "minor_version", "patch_version"
        ),
        Index("idx_projects_version_locked", "version_locked"),
    )

    @hybrid_property
    def version_string(self) -> str:
        """Generate version string from major.minor.patch"""
        return f"{self.major_version}.{self.minor_version}.{self.patch_version}"

    def increment_version(
        self,
        change_type: str,
        entity_type: str,
        entity_id: uuid.UUID,
        modified_by: str,
        description: Optional[str] = None,
    ) -> str:
        """Increment project version based on change type"""
        old_version = self.version_string

        if change_type == "major":
            self.major_version += 1
            self.minor_version = 0
            self.patch_version = 0
        elif change_type == "minor":
            self.minor_version += 1
            self.patch_version = 0
        elif change_type == "patch":
            self.patch_version += 1
        else:
            raise ValueError(
                f"Invalid change_type: {change_type}. Must be major, minor, or patch"
            )

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

    __tablename__ = "project_version_history"

    version_history_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
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
        Index("idx_project_version_history_project_id", "project_id"),
        Index("idx_project_version_history_created_at", "created_at"),
    )


class Dataset(Base, TimestampMixin, EntityVersionMixin):
    """Collections of tables within a project"""

    __tablename__ = "datasets"

    dataset_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    dataset_metadata = Column(JSONB)

    # Relationships
    project = relationship("Project", back_populates="datasets")
    tables = relationship(
        "Table", back_populates="dataset", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_datasets_project_name"),
        Index("idx_datasets_project_id", "project_id"),
        Index("idx_datasets_entity_version", "entity_version"),
    )


class Table(Base, TimestampMixin, EntityVersionMixin):
    """Individual data tables with descriptions"""

    __tablename__ = "tables"

    table_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(
        UUID(as_uuid=True), ForeignKey("datasets.dataset_id", ondelete="CASCADE")
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    mdl_file = Column(String(200))
    ddl_file = Column(String(200))
    table_type = Column(String(20), default="table", nullable=False)
    table_metadata = Column(JSONB)

    # Relationships
    project = relationship("Project", back_populates="tables")
    dataset = relationship("Dataset", back_populates="tables")
    columns = relationship(
        "Columns", back_populates="table", cascade="all, delete-orphan"
    )
    metrics = relationship(
        "Metric", back_populates="table", cascade="all, delete-orphan"
    )
    views = relationship("View", back_populates="table", cascade="all, delete-orphan")
    from_relationships = relationship(
        "Relationship",
        foreign_keys="[Relationship.from_table_id]",
        back_populates="from_table",
    )
    to_relationships = relationship(
        "Relationship",
        foreign_keys="[Relationship.to_table_id]",
        back_populates="to_table",
    )

    __table_args__ = (
        CheckConstraint(
            "table_type IN ('table', 'view', 'materialized_view')",
            name="check_table_type",
        ),
        UniqueConstraint("project_id", "name", name="uq_tables_project_name"),
        Index("idx_tables_project_id", "project_id"),
        Index("idx_tables_dataset_id", "dataset_id"),
        Index("idx_tables_entity_version", "entity_version"),
    )


class Columns(Base, TimestampMixin, EntityVersionMixin):
    """Table columns with comprehensive metadata"""

    __tablename__ = "columns"

    column_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    column_type = Column(String(20), default="column", nullable=False)
    data_type = Column(String(50))
    usage_type = Column(String(50))
    is_nullable = Column(Boolean, default=True)
    is_primary_key = Column(Boolean, default=False)
    is_foreign_key = Column(Boolean, default=False)
    default_value = Column(Text)
    ordinal_position = Column(Integer)
    column_metadata = Column(JSONB)

    # Relationships
    table = relationship("Table", back_populates="columns")
    calculated_column = relationship(
        "CalculatedColumn",
        back_populates="column",
        uselist=False,
        cascade="all, delete-orphan",
    )
    from_relationships = relationship(
        "Relationship",
        foreign_keys="[Relationship.from_column_id]",
        back_populates="from_column",
    )
    to_relationships = relationship(
        "Relationship",
        foreign_keys="[Relationship.to_column_id]",
        back_populates="to_column",
    )

    __table_args__ = (
        CheckConstraint(
            "column_type IN ('column', 'calculated_column')", name="check_column_type"
        ),
        UniqueConstraint("table_id", "name", name="uq_columns_table_name"),
        Index("idx_columns_table_id", "table_id"),
        Index("idx_columns_type", "column_type"),
        Index("idx_columns_entity_version", "entity_version"),
    )


class SQLFunction(Base, TimestampMixin, EntityVersionMixin):
    """Project-level reusable functions"""

    __tablename__ = "sql_functions"

    function_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    function_sql = Column(Text, nullable=False)
    return_type = Column(String(50))
    parameters = Column(JSONB)

    # Relationships
    project = relationship("Project", back_populates="sql_functions")
    calculated_columns = relationship("CalculatedColumn", back_populates="function")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_sql_functions_project_name"),
    )


class CalculatedColumn(Base, TimestampMixin, EntityVersionMixin):
    """Special columns with associated functions"""

    __tablename__ = "calculated_columns"

    calculated_column_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    column_id = Column(
        UUID(as_uuid=True),
        ForeignKey("columns.column_id", ondelete="CASCADE"),
        nullable=False,
    )
    calculation_sql = Column(Text, nullable=False)
    function_id = Column(UUID(as_uuid=True), ForeignKey("sql_functions.function_id"))
    dependencies = Column(JSONB)

    # Relationships
    column = relationship("Columns", back_populates="calculated_column")
    function = relationship("SQLFunction", back_populates="calculated_columns")


class Metric(Base, TimestampMixin, EntityVersionMixin):
    """Table-level metrics and KPIs"""

    __tablename__ = "metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    metric_sql = Column(Text, nullable=False)
    metric_type = Column(String(50))
    aggregation_type = Column(String(50))
    format_string = Column(String(50))
    metric_metadata = Column(JSONB)

    # Relationships
    table = relationship("Table", back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("table_id", "name", name="uq_metrics_table_name"),
    )


class View(Base, TimestampMixin, EntityVersionMixin):
    """Table views and perspectives"""

    __tablename__ = "views"

    view_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    view_sql = Column(Text, nullable=False)
    view_type = Column(String(50))
    view_metadata = Column(JSONB)

    # Relationships
    table = relationship("Table", back_populates="views")

    __table_args__ = (UniqueConstraint("table_id", "name", name="uq_views_table_name"),)


class Relationship(Base, TimestampMixin, EntityVersionMixin):
    """Define relationships between tables/datasets"""

    __tablename__ = "relationships"

    relationship_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100))
    relationship_type = Column(String(50), nullable=False)
    from_table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=False,
    )
    to_table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=False,
    )
    from_column_id = Column(UUID(as_uuid=True), ForeignKey("columns.column_id"))
    to_column_id = Column(UUID(as_uuid=True), ForeignKey("columns.column_id"))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    relationship_metadata = Column(JSONB)

    # Relationships
    project = relationship("Project", back_populates="relationships")
    from_table = relationship(
        "Table", foreign_keys=[from_table_id], back_populates="from_relationships"
    )
    to_table = relationship(
        "Table", foreign_keys=[to_table_id], back_populates="to_relationships"
    )
    from_column = relationship(
        "Columns", foreign_keys=[from_column_id], back_populates="from_relationships"
    )
    to_column = relationship(
        "Columns", foreign_keys=[to_column_id], back_populates="to_relationships"
    )

    __table_args__ = (
        Index("idx_relationships_project_id", "project_id"),
        Index("idx_relationships_from_table", "from_table_id"),
        Index("idx_relationships_to_table", "to_table_id"),
    )


class Instruction(Base, TimestampMixin, EntityVersionMixin):
    """Each instruction item as a row (from instructions.json)"""

    __tablename__ = "instructions"

    instruction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    question = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    chain_of_thought = Column(Text)
    instruction_metadata = Column(JSONB)

    # Relationships
    project = relationship("Project", back_populates="instructions")

    __table_args__ = (Index("idx_instructions_project_id", "project_id"),)


class Example(Base, TimestampMixin, EntityVersionMixin):
    """Each SQL pair item as a row (from sql_pairs.json)"""

    __tablename__ = "examples"

    example_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    question = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    context = Column(Text)
    document_reference = Column(String(200))
    instructions = Column(Text)
    categories = Column(JSONB)  # Array of category strings
    samples = Column(JSONB)  # Array of sample data
    example_metadata = Column(JSONB)

    # Relationships
    project = relationship("Project", back_populates="examples")

    __table_args__ = (Index("idx_examples_project_id", "project_id"),)


class KnowledgeBase(Base, TimestampMixin, EntityVersionMixin):
    """Project knowledge base entries"""

    __tablename__ = "knowledge_base"

    kb_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    file_path = Column(String(500))
    content_type = Column(String(50))
    content = Column(Text)
    kb_metadata = Column(JSONB)

    # Relationships
    project = relationship("Project", back_populates="knowledge_base")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_knowledge_base_project_name"),
        Index("idx_knowledge_base_project_id", "project_id"),
    )


class ProjectHistory(Base, TimestampMixin):
    """Track changes and versions"""

    __tablename__ = "project_histories"

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    table_id = Column(UUID(as_uuid=True), ForeignKey("tables.table_id"))
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
        Index("idx_project_histories_project_id", "project_id"),
        Index("idx_project_histories_entity", "entity_type", "entity_id"),
        Index("idx_project_histories_changed_at", "created_at"),
    )
