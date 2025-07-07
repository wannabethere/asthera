"""
Async Project Management Service
Clean and simple service for managing projects with tables, drafts, and publishing workflow
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, func
from pydantic import BaseModel, Field, ConfigDict
import asyncpg
from app.service.models import ProjectCreate, TableCreate, ColumnCreate, MetricCreate, ViewCreate, CalculatedColumnCreate, ProjectResponse, TableResponse
from app.schemas.dbmodels import Project, Table, SQLColumn, Metric, View, CalculatedColumn

logger = logging.getLogger(__name__)

# ============================================================================
# SERVICE LAYER
# ============================================================================

class ProjectService:
    """Main service for project management operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_project(self, project_data: ProjectCreate) -> Project:
        """Create a new project in draft status"""
        # Check if project already exists
        existing = await self.db.execute(
            select(Project).where(Project.project_id == project_data.project_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with ID {project_data.project_id} already exists"
            )
        
        project = Project(
            project_id=project_data.project_id,
            display_name=project_data.display_name,
            description=project_data.description,
            created_by=project_data.created_by,
            status='draft',  # Start as draft
            version_locked=True  # Lock version during draft phase
        )
        
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project
    
    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID with tables"""
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.tables))
            .where(Project.project_id == project_id)
        )
        return result.scalar_one_or_none()
    
    async def add_table_to_project(self, project_id: str, table_data: TableCreate, created_by: str) -> Table:
        """Add a table to project (max 4 tables)"""
        # Check if project exists and is in draft
        project = await self.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        if project.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add tables to draft projects"
            )
        
        # Check table limit (3-4 tables max)
        table_count = len(project.tables)
        if table_count >= 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project can have maximum 4 tables"
            )
        
        # Check for duplicate table name
        existing_table = await self.db.execute(
            select(Table).where(
                Table.project_id == project_id,
                Table.name == table_data.name
            )
        )
        if existing_table.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table '{table_data.name}' already exists in project"
            )
        
        table = Table(
            project_id=project_id,
            dataset_id=table_data.dataset_id,
            name=table_data.name,
            display_name=table_data.display_name or table_data.name,
            description=table_data.description,
            table_type=table_data.table_type,
            modified_by=created_by
        )
        
        self.db.add(table)
        await self.db.commit()
        await self.db.refresh(table)
        return table
    
    async def add_columns_to_table(self, table_id: str, columns: List[ColumnCreate], created_by: str) -> List[SQLColumn]:
        """Add columns to a table"""
        # Verify table exists
        table = await self.db.execute(
            select(Table).where(Table.table_id == table_id)
        )
        table = table.scalar_one_or_none()
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_id} not found"
            )
        
        created_columns = []
        for i, col_data in enumerate(columns):
            column = SQLColumn(
                table_id=table_id,
                name=col_data.name,
                display_name=col_data.display_name or col_data.name,
                description=col_data.description,
                data_type=col_data.data_type,
                is_nullable=col_data.is_nullable,
                is_primary_key=col_data.is_primary_key,
                ordinal_position=i + 1,
                modified_by=created_by
            )
            self.db.add(column)
            created_columns.append(column)
        
        await self.db.commit()
        for col in created_columns:
            await self.db.refresh(col)
        
        return created_columns
    
    async def generate_semantic_descriptions(self, project_id: str) -> Dict[str, Dict[str, Any]]:
        """Generate semantic descriptions for all tables in project"""
        project = await self.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        descriptions = {}
        for table in project.tables:
            # Generate semantic description using the service
            semantic_result = await self._generate_table_semantic_description(table)
            descriptions[table.table_id] = semantic_result
            
            # Update table with semantic description metadata
            await self.db.execute(
                update(Table)
                .where(Table.table_id == table.table_id)
                .values(json_metadata={
                    'semantic_description': semantic_result.get('description', ''),
                    'semantic_analysis': semantic_result
                })
            )
        
        await self.db.commit()
        return descriptions
    
    async def _generate_table_semantic_description(self, table: Table) -> Dict[str, Any]:
        """Generate semantic description using the semantics description service"""
        try:
            from app.agents.semantics_description import SemanticsDescription
            
            # Convert table to the format expected by the semantics description service
            table_data = {
                "name": table.name,
                "display_name": table.display_name,
                "description": table.description,
                "columns": []
            }
            
            # Get columns for this table
            columns_result = await self.db.execute(
                select(SQLColumn).where(SQLColumn.table_id == table.table_id)
            )
            columns = columns_result.scalars().all()
            
            # Convert columns to the expected format
            for col in columns:
                column_data = {
                    "name": col.name,
                    "display_name": col.display_name,
                    "description": col.description,
                    "data_type": col.data_type,
                    "is_primary_key": col.is_primary_key,
                    "is_nullable": col.is_nullable,
                    "usage_type": col.usage_type
                }
                table_data["columns"].append(column_data)
            
            # Create semantics description service instance
            semantics_service = SemanticsDescription()
            
            # Generate description
            result = await semantics_service.describe(
                SemanticsDescription.Input(
                    id=f"table_{table.table_id}",
                    table_data=table_data,
                    project_id=table.project_id
                )
            )
            
            if result.status == "finished" and result.response:
                # Return the full response
                return result.response
            else:
                logger.error(f"Failed to generate semantic description for table {table.table_id}: {result.error}")
                # Return fallback response
                return {
                    "description": f"Semantic description for {table.display_name}: This table contains {table.description or 'data related to the business domain'}. Generated automatically based on table structure and content.",
                    "table_purpose": f"Stores {table.description or 'data'} for {table.display_name}",
                    "key_columns": [],
                    "business_context": f"This table supports the business domain by storing {table.description or 'relevant data'}.",
                    "data_patterns": ["Data storage", "Information management"],
                    "suggested_relationships": []
                }
                
        except Exception as e:
            logger.error(f"Error generating semantic description for table {table.table_id}: {str(e)}")
            # Return fallback response
            return {
                "description": f"Semantic description for {table.display_name}: This table contains {table.description or 'data related to the business domain'}. Generated automatically based on table structure and content.",
                "table_purpose": f"Stores {table.description or 'data'} for {table.display_name}",
                "key_columns": [],
                "business_context": f"This table supports the business domain by storing {table.description or 'relevant data'}.",
                "data_patterns": ["Data storage", "Information management"],
                "suggested_relationships": []
            }
    
    async def save_as_draft(self, project_id: str) -> Project:
        """Finalize project as draft (ready for metrics/views)"""
        project = await self.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        if len(project.tables) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project must have at least one table to save as draft"
            )
        
        # Update project status
        await self.db.execute(
            update(Project)
            .where(Project.project_id == project_id)
            .values(
                status='draft_ready',  # Ready for metrics/views
                updated_at=func.now()
            )
        )
        
        await self.db.commit()
        return await self.get_project(project_id)
    
    async def publish_project(self, project_id: str, published_by: str) -> Project:
        """Publish project (final step)"""
        project = await self.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        if project.status not in ['draft_ready', 'review']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project must be in review status to publish"
            )
        
        # Unlock version and publish
        await self.db.execute(
            update(Project)
            .where(Project.project_id == project_id)
            .values(
                status='active',
                version_locked=False,
                last_modified_by=published_by,
                updated_at=func.now()
            )
        )
        
        await self.db.commit()
        return await self.get_project(project_id)

class MetricsService:
    """Service for managing metrics, views, and calculated columns"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_metric(self, table_id: str, metric_data: MetricCreate, created_by: str) -> Metric:
        """Add metric to table"""
        metric = Metric(
            table_id=table_id,
            name=metric_data.name,
            display_name=metric_data.display_name or metric_data.name,
            description=metric_data.description,
            metric_sql=metric_data.metric_sql,
            metric_type=metric_data.metric_type,
            aggregation_type=metric_data.aggregation_type,
            modified_by=created_by
        )
        
        self.db.add(metric)
        await self.db.commit()
        await self.db.refresh(metric)
        return metric
    
    async def add_view(self, table_id: str, view_data: ViewCreate, created_by: str) -> View:
        """Add view to table"""
        view = View(
            table_id=table_id,
            name=view_data.name,
            display_name=view_data.display_name or view_data.name,
            description=view_data.description,
            view_sql=view_data.view_sql,
            view_type=view_data.view_type,
            modified_by=created_by
        )
        
        self.db.add(view)
        await self.db.commit()
        await self.db.refresh(view)
        return view
    
    async def add_calculated_column(self, table_id: str, calc_data: CalculatedColumnCreate, created_by: str) -> SQLColumn:
        """Add calculated column as a SQLColumn with type 'calculated_column'"""
        # First create the SQLColumn with type 'calculated_column'
        column = SQLColumn(
            table_id=table_id,
            name=calc_data.name,
            display_name=calc_data.display_name or calc_data.name,
            description=calc_data.description,
            column_type='calculated_column',  # Mark as calculated column
            data_type=calc_data.data_type,
            usage_type=calc_data.usage_type,
            is_nullable=calc_data.is_nullable,
            is_primary_key=calc_data.is_primary_key,
            is_foreign_key=calc_data.is_foreign_key,
            default_value=calc_data.default_value,
            ordinal_position=calc_data.ordinal_position,
            json_metadata=calc_data.metadata,
            modified_by=created_by
        )
        
        self.db.add(column)
        await self.db.commit()
        await self.db.refresh(column)
        
        # Then create the associated CalculatedColumn with the calculation details
        calc_column = CalculatedColumn(
            column_id=column.column_id,
            calculation_sql=calc_data.calculation_sql,
            function_id=calc_data.function_id,
            dependencies=calc_data.dependencies,
            modified_by=created_by
        )
        
        self.db.add(calc_column)
        await self.db.commit()
        await self.db.refresh(calc_column)
        
        return column

# ============================================================================
# API ENDPOINTS
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db_manager.initialize()
    yield
    # Shutdown
    await db_manager.close()

app = FastAPI(
    title="Project Management Service",
    description="Clean async service for managing projects with tables and publishing workflow",
    version="1.0.0",
    lifespan=lifespan
)

# Project endpoints
@app.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project_data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new project"""
    service = ProjectService(db)
    project = await service.create_project(project_data)
    
    return ProjectResponse(
        project_id=project.project_id,
        display_name=project.display_name,
        description=project.description,
        status=project.status,
        is_draft=project.status.startswith('draft'),
        version_string=project.version_string,
        created_at=project.created_at,
        table_count=0
    )

@app.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get project details"""
    service = ProjectService(db)
    project = await service.get_project(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    
    return ProjectResponse(
        project_id=project.project_id,
        display_name=project.display_name,
        description=project.description,
        status=project.status,
        is_draft=project.status.startswith('draft'),
        version_string=project.version_string,
        created_at=project.created_at,
        table_count=len(project.tables)
    )

@app.post("/projects/{project_id}/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def add_table(project_id: str, table_data: TableCreate, created_by: str = "user", db: AsyncSession = Depends(get_db)):
    """Add table to project"""
    service = ProjectService(db)
    table = await service.add_table_to_project(project_id, table_data, created_by)
    
    return TableResponse(
        table_id=table.table_id,
        name=table.name,
        display_name=table.display_name,
        description=table.description,
        table_type=table.table_type,
        column_count=0
    )

@app.post("/tables/{table_id}/columns", status_code=status.HTTP_201_CREATED)
async def add_columns(table_id: str, columns: List[ColumnCreate], created_by: str = "user", db: AsyncSession = Depends(get_db)):
    """Add columns to table"""
    service = ProjectService(db)
    created_columns = await service.add_columns_to_table(table_id, columns, created_by)
    return {"message": f"Added {len(created_columns)} columns to table", "column_count": len(created_columns)}

@app.post("/projects/{project_id}/generate-descriptions")
async def generate_descriptions(project_id: str, db: AsyncSession = Depends(get_db)):
    """Generate semantic descriptions for all tables"""
    service = ProjectService(db)
    descriptions = await service.generate_semantic_descriptions(project_id)
    return {"project_id": project_id, "descriptions": descriptions}

@app.post("/projects/{project_id}/save-draft")
async def save_draft(project_id: str, db: AsyncSession = Depends(get_db)):
    """Save project as draft (ready for metrics/views)"""
    service = ProjectService(db)
    project = await service.save_as_draft(project_id)
    return {"message": "Project saved as draft", "status": project.status}

@app.post("/projects/{project_id}/publish")
async def publish_project(project_id: str, published_by: str = "admin", db: AsyncSession = Depends(get_db)):
    """Publish project"""
    service = ProjectService(db)
    project = await service.publish_project(project_id, published_by)
    return {"message": "Project published successfully", "status": project.status}

# Metrics/Views endpoints (second service)
@app.post("/tables/{table_id}/metrics", status_code=status.HTTP_201_CREATED)
async def add_metric(table_id: str, metric_data: MetricCreate, created_by: str = "user", db: AsyncSession = Depends(get_db)):
    """Add metric to table using LLMDefinitionGenerator for enhancement"""
    service = MetricsService(db)
    metric = await service.add_metric(table_id, metric_data, created_by)
    return {
        "metric_id": metric.metric_id, 
        "name": metric.name,
        "display_name": metric.display_name,
        "enhanced": metric.json_metadata.get("generated_by") == "llm_definition_generator" if metric.json_metadata else False,
        "confidence_score": metric.json_metadata.get("confidence_score") if metric.json_metadata else None
    }

@app.post("/tables/{table_id}/views", status_code=status.HTTP_201_CREATED)
async def add_view(table_id: str, view_data: ViewCreate, created_by: str = "user", db: AsyncSession = Depends(get_db)):
    """Add view to table using LLMDefinitionGenerator for enhancement"""
    service = MetricsService(db)
    view = await service.add_view(table_id, view_data, created_by)
    return {
        "view_id": view.view_id, 
        "name": view.name,
        "display_name": view.display_name,
        "enhanced": view.json_metadata.get("generated_by") == "llm_definition_generator" if view.json_metadata else False,
        "confidence_score": view.json_metadata.get("confidence_score") if view.json_metadata else None
    }

@app.post("/tables/{table_id}/calculated-columns", status_code=status.HTTP_201_CREATED)
async def add_calculated_column(table_id: str, calc_data: CalculatedColumnCreate, created_by: str = "user", db: AsyncSession = Depends(get_db)):
    """Add calculated column to table using LLMDefinitionGenerator for enhancement"""
    service = MetricsService(db)
    column = await service.add_calculated_column(table_id, calc_data.dict(), created_by)
    return {
        "column_id": column.column_id,
        "name": column.name,
        "display_name": column.display_name,
        "column_type": column.column_type,
        "enhanced": column.json_metadata.get("generated_by") == "llm_definition_generator" if column.json_metadata else False,
        "confidence_score": column.json_metadata.get("confidence_score") if column.json_metadata else None,
        "message": f"Calculated column '{column.name}' added successfully"
    }

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)