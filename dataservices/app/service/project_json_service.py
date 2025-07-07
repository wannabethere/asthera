"""
Service for managing project JSON data with ChromaDB integration
Handles storing and retrieving project JSON data with vector search capabilities
"""

import uuid
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.schemas.dbmodels import ProjectJSONStore, Project, Table, Metric, View, SQLColumn, CalculatedColumn
from app.storage.chromadb import ChromaDB
from app.core.session_manager import SessionManager
from app.utils.history import ProjectManager

import logging

logger = logging.getLogger(__name__)


class ProjectJSONService:
    """Service for managing project JSON data with ChromaDB integration"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager):
        self.session_manager = session_manager
        self.project_manager = project_manager
        self.chroma_client = ChromaDB()
        self.collection_name = "project_json_store"
    
    async def store_project_tables_json(self, project_id: str, updated_by: str = 'system') -> str:
        """Store project tables JSON in ChromaDB and PostgreSQL"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Get project and its tables
                project = await self._get_project(session, project_id)
                tables = await self._get_project_tables(session, project_id)
                
                # Build tables JSON
                tables_json = {
                    "project_id": project_id,
                    "project_name": project.display_name,
                    "tables": []
                }
                
                for table in tables:
                    table_data = {
                        "table_id": table.table_id,
                        "name": table.name,
                        "display_name": table.display_name,
                        "description": table.description,
                        "table_type": table.table_type,
                        "columns": []
                    }
                    
                    # Add columns
                    for column in table.columns:
                        column_data = {
                            "column_id": column.column_id,
                            "name": column.name,
                            "display_name": column.display_name,
                            "description": column.description,
                            "data_type": column.data_type,
                            "usage_type": column.usage_type,
                            "is_nullable": column.is_nullable,
                            "is_primary_key": column.is_primary_key,
                            "is_foreign_key": column.is_foreign_key,
                            "default_value": column.default_value,
                            "ordinal_position": column.ordinal_position
                        }
                        
                        # Add calculated column info if exists
                        if column.calculated_column:
                            column_data["calculated_column"] = {
                                "calculation_sql": column.calculated_column.calculation_sql,
                                "function_id": column.calculated_column.function_id,
                                "dependencies": column.calculated_column.dependencies
                            }
                        
                        table_data["columns"].append(column_data)
                    
                    tables_json["tables"].append(table_data)
                
                # Store in ChromaDB
                chroma_doc_id = await self._store_in_chromadb(
                    collection_name=self.collection_name,
                    document_content=json.dumps(tables_json, default=str),
                    metadata={
                        "project_id": project_id,
                        "json_type": "tables",
                        "table_count": len(tables),
                        "total_columns": sum(len(t.columns) for t in tables),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
                
                # Store reference in PostgreSQL
                await self._store_json_reference(
                    session=session,
                    project_id=project_id,
                    json_type="tables",
                    chroma_document_id=chroma_doc_id,
                    json_content=tables_json,
                    updated_by=updated_by,
                    update_reason="Tables JSON updated"
                )
                
                logger.info(f"Stored tables JSON for project {project_id} with ChromaDB ID: {chroma_doc_id}")
                return chroma_doc_id
                
            except Exception as e:
                logger.error(f"Failed to store tables JSON for project {project_id}: {str(e)}")
                raise Exception(f"Failed to store tables JSON: {str(e)}")
    
    async def store_project_metrics_json(self, project_id: str, updated_by: str = 'system') -> str:
        """Store project metrics JSON in ChromaDB and PostgreSQL"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Get project and its metrics
                project = await self._get_project(session, project_id)
                metrics = await self._get_project_metrics(session, project_id)
                
                # Build metrics JSON
                metrics_json = {
                    "project_id": project_id,
                    "project_name": project.display_name,
                    "metrics": []
                }
                
                for metric in metrics:
                    metric_data = {
                        "metric_id": metric.metric_id,
                        "name": metric.name,
                        "display_name": metric.display_name,
                        "description": metric.description,
                        "metric_sql": metric.metric_sql,
                        "metric_type": metric.metric_type,
                        "aggregation_type": metric.aggregation_type,
                        "format_string": metric.format_string,
                        "table_id": metric.table_id,
                        "table_name": metric.table.name if metric.table else None,
                        "metadata": metric.json_metadata
                    }
                    metrics_json["metrics"].append(metric_data)
                
                # Store in ChromaDB
                chroma_doc_id = await self._store_in_chromadb(
                    collection_name=self.collection_name,
                    document_content=json.dumps(metrics_json, default=str),
                    metadata={
                        "project_id": project_id,
                        "json_type": "metrics",
                        "metric_count": len(metrics),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
                
                # Store reference in PostgreSQL
                await self._store_json_reference(
                    session=session,
                    project_id=project_id,
                    json_type="metrics",
                    chroma_document_id=chroma_doc_id,
                    json_content=metrics_json,
                    updated_by=updated_by,
                    update_reason="Metrics JSON updated"
                )
                
                logger.info(f"Stored metrics JSON for project {project_id} with ChromaDB ID: {chroma_doc_id}")
                return chroma_doc_id
                
            except Exception as e:
                logger.error(f"Failed to store metrics JSON for project {project_id}: {str(e)}")
                raise Exception(f"Failed to store metrics JSON: {str(e)}")
    
    async def store_project_views_json(self, project_id: str, updated_by: str = 'system') -> str:
        """Store project views JSON in ChromaDB and PostgreSQL"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Get project and its views
                project = await self._get_project(session, project_id)
                views = await self._get_project_views(session, project_id)
                
                # Build views JSON
                views_json = {
                    "project_id": project_id,
                    "project_name": project.display_name,
                    "views": []
                }
                
                for view in views:
                    view_data = {
                        "view_id": view.view_id,
                        "name": view.name,
                        "display_name": view.display_name,
                        "description": view.description,
                        "view_sql": view.view_sql,
                        "view_type": view.view_type,
                        "table_id": view.table_id,
                        "table_name": view.table.name if view.table else None,
                        "metadata": view.json_metadata
                    }
                    views_json["views"].append(view_data)
                
                # Store in ChromaDB
                chroma_doc_id = await self._store_in_chromadb(
                    collection_name=self.collection_name,
                    document_content=json.dumps(views_json, default=str),
                    metadata={
                        "project_id": project_id,
                        "json_type": "views",
                        "view_count": len(views),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
                
                # Store reference in PostgreSQL
                await self._store_json_reference(
                    session=session,
                    project_id=project_id,
                    json_type="views",
                    chroma_document_id=chroma_doc_id,
                    json_content=views_json,
                    updated_by=updated_by,
                    update_reason="Views JSON updated"
                )
                
                logger.info(f"Stored views JSON for project {project_id} with ChromaDB ID: {chroma_doc_id}")
                return chroma_doc_id
                
            except Exception as e:
                logger.error(f"Failed to store views JSON for project {project_id}: {str(e)}")
                raise Exception(f"Failed to store views JSON: {str(e)}")
    
    async def store_project_calculated_columns_json(self, project_id: str, updated_by: str = 'system') -> str:
        """Store project calculated columns JSON in ChromaDB and PostgreSQL"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Get project and its calculated columns
                project = await self._get_project(session, project_id)
                calculated_columns = await self._get_project_calculated_columns(session, project_id)
                
                # Build calculated columns JSON
                calc_columns_json = {
                    "project_id": project_id,
                    "project_name": project.display_name,
                    "calculated_columns": []
                }
                
                for calc_col in calculated_columns:
                    calc_col_data = {
                        "calculated_column_id": calc_col.calculated_column_id,
                        "column_id": calc_col.column_id,
                        "calculation_sql": calc_col.calculation_sql,
                        "function_id": calc_col.function_id,
                        "dependencies": calc_col.dependencies,
                        "column_name": calc_col.column.name if calc_col.column else None,
                        "table_name": calc_col.column.table.name if calc_col.column and calc_col.column.table else None,
                        "table_id": calc_col.column.table_id if calc_col.column else None
                    }
                    calc_columns_json["calculated_columns"].append(calc_col_data)
                
                # Store in ChromaDB
                chroma_doc_id = await self._store_in_chromadb(
                    collection_name=self.collection_name,
                    document_content=json.dumps(calc_columns_json, default=str),
                    metadata={
                        "project_id": project_id,
                        "json_type": "calculated_columns",
                        "calculated_column_count": len(calculated_columns),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
                
                # Store reference in PostgreSQL
                await self._store_json_reference(
                    session=session,
                    project_id=project_id,
                    json_type="calculated_columns",
                    chroma_document_id=chroma_doc_id,
                    json_content=calc_columns_json,
                    updated_by=updated_by,
                    update_reason="Calculated columns JSON updated"
                )
                
                logger.info(f"Stored calculated columns JSON for project {project_id} with ChromaDB ID: {chroma_doc_id}")
                return chroma_doc_id
                
            except Exception as e:
                logger.error(f"Failed to store calculated columns JSON for project {project_id}: {str(e)}")
                raise Exception(f"Failed to store calculated columns JSON: {str(e)}")
    
    async def store_project_summary_json(self, project_id: str, updated_by: str = 'system') -> str:
        """Store complete project summary JSON in ChromaDB and PostgreSQL"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Get project and all related data
                project = await self._get_project(session, project_id)
                tables = await self._get_project_tables(session, project_id)
                metrics = await self._get_project_metrics(session, project_id)
                views = await self._get_project_views(session, project_id)
                calculated_columns = await self._get_project_calculated_columns(session, project_id)
                
                # Build comprehensive project JSON
                project_json = {
                    "project_id": project_id,
                    "project_name": project.display_name,
                    "description": project.description,
                    "status": project.status,
                    "version": project.version_string,
                    "summary": {
                        "table_count": len(tables),
                        "metric_count": len(metrics),
                        "view_count": len(views),
                        "calculated_column_count": len(calculated_columns),
                        "total_columns": sum(len(t.columns) for t in tables)
                    },
                    "tables": [{"table_id": t.table_id, "name": t.name, "display_name": t.display_name} for t in tables],
                    "metrics": [{"metric_id": m.metric_id, "name": m.name, "display_name": m.display_name} for m in metrics],
                    "views": [{"view_id": v.view_id, "name": v.name, "display_name": v.display_name} for v in views],
                    "calculated_columns": [{"calculated_column_id": c.calculated_column_id, "column_name": c.column.name if c.column else None} for c in calculated_columns],
                    "metadata": project.json_metadata
                }
                
                # Store in ChromaDB
                chroma_doc_id = await self._store_in_chromadb(
                    collection_name=self.collection_name,
                    document_content=json.dumps(project_json, default=str),
                    metadata={
                        "project_id": project_id,
                        "json_type": "project_summary",
                        "table_count": len(tables),
                        "metric_count": len(metrics),
                        "view_count": len(views),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
                
                # Store reference in PostgreSQL
                await self._store_json_reference(
                    session=session,
                    project_id=project_id,
                    json_type="project_summary",
                    chroma_document_id=chroma_doc_id,
                    json_content=project_json,
                    updated_by=updated_by,
                    update_reason="Project summary JSON updated"
                )
                
                logger.info(f"Stored project summary JSON for project {project_id} with ChromaDB ID: {chroma_doc_id}")
                return chroma_doc_id
                
            except Exception as e:
                logger.error(f"Failed to store project summary JSON for project {project_id}: {str(e)}")
                raise Exception(f"Failed to store project summary JSON: {str(e)}")
    
    async def get_project_json(self, project_id: str, json_type: str) -> Optional[Dict[str, Any]]:
        """Get project JSON data by type"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Get the JSON store record
                result = await session.execute(
                    select(ProjectJSONStore).where(
                        ProjectJSONStore.project_id == project_id,
                        ProjectJSONStore.json_type == json_type,
                        ProjectJSONStore.is_active == True
                    )
                )
                json_store = result.scalar_one_or_none()
                
                if not json_store:
                    return None
                
                return json_store.json_content
                
            except Exception as e:
                logger.error(f"Failed to get project JSON for project {project_id}, type {json_type}: {str(e)}")
                raise Exception(f"Failed to get project JSON: {str(e)}")
    
    async def search_project_json(self, project_id: str, search_query: str, json_type: Optional[str] = None, n_results: int = 10) -> List[Dict[str, Any]]:
        """Search project JSON data using ChromaDB"""
        try:
            # Build search metadata
            where_metadata = {"project_id": project_id}
            if json_type:
                where_metadata["json_type"] = json_type
            
            # Search in ChromaDB
            search_results = self.chroma_client.query_collection(
                collection_name=self.collection_name,
                query_texts=[search_query],
                n_results=n_results,
                where=where_metadata
            )
            
            # Process results
            results = []
            if search_results and 'documents' in search_results:
                for i, doc in enumerate(search_results['documents'][0]):
                    results.append({
                        "document": doc,
                        "distance": search_results['distances'][0][i] if 'distances' in search_results else None
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search project JSON for project {project_id}: {str(e)}")
            raise Exception(f"Failed to search project JSON: {str(e)}")
    
    async def update_project_json_on_change(self, project_id: str, entity_type: str, entity_id: str, updated_by: str = 'system') -> List[str]:
        """Update relevant JSON stores when project entities change"""
        try:
            updated_doc_ids = []
            
            # Determine which JSON types need updating based on entity type
            json_types_to_update = []
            
            if entity_type in ['table', 'column']:
                json_types_to_update.extend(['tables', 'project_summary'])
            elif entity_type == 'metric':
                json_types_to_update.extend(['metrics', 'project_summary'])
            elif entity_type == 'view':
                json_types_to_update.extend(['views', 'project_summary'])
            elif entity_type == 'calculated_column':
                json_types_to_update.extend(['calculated_columns', 'tables', 'project_summary'])
            
            # Update each JSON type
            for json_type in json_types_to_update:
                if json_type == 'tables':
                    doc_id = await self.store_project_tables_json(project_id, updated_by)
                elif json_type == 'metrics':
                    doc_id = await self.store_project_metrics_json(project_id, updated_by)
                elif json_type == 'views':
                    doc_id = await self.store_project_views_json(project_id, updated_by)
                elif json_type == 'calculated_columns':
                    doc_id = await self.store_project_calculated_columns_json(project_id, updated_by)
                elif json_type == 'project_summary':
                    doc_id = await self.store_project_summary_json(project_id, updated_by)
                
                updated_doc_ids.append(doc_id)
            
            logger.info(f"Updated JSON stores for project {project_id}: {json_types_to_update}")
            return updated_doc_ids
            
        except Exception as e:
            logger.error(f"Failed to update project JSON on change for project {project_id}: {str(e)}")
            raise Exception(f"Failed to update project JSON on change: {str(e)}")
    
    # Helper methods
    async def _get_project(self, session: Session, project_id: str) -> Project:
        """Get project by ID"""
        result = await session.execute(
            select(Project).where(Project.project_id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")
        return project
    
    async def _get_project_tables(self, session: Session, project_id: str) -> List[Table]:
        """Get all tables for a project"""
        result = await session.execute(
            select(Table).where(Table.project_id == project_id)
        )
        return result.scalars().all()
    
    async def _get_project_metrics(self, session: Session, project_id: str) -> List[Metric]:
        """Get all metrics for a project"""
        result = await session.execute(
            select(Metric).join(Table).where(Table.project_id == project_id)
        )
        return result.scalars().all()
    
    async def _get_project_views(self, session: Session, project_id: str) -> List[View]:
        """Get all views for a project"""
        result = await session.execute(
            select(View).join(Table).where(Table.project_id == project_id)
        )
        return result.scalars().all()
    
    async def _get_project_calculated_columns(self, session: Session, project_id: str) -> List[CalculatedColumn]:
        """Get all calculated columns for a project"""
        result = await session.execute(
            select(CalculatedColumn).join(SQLColumn).join(Table).where(Table.project_id == project_id)
        )
        return result.scalars().all()
    
    async def _store_in_chromadb(self, collection_name: str, document_content: str, metadata: Dict[str, Any]) -> str:
        """Store document in ChromaDB"""
        doc_id = str(uuid.uuid4())
        
        self.chroma_client.add_documents(
            collection_name=collection_name,
            documents=[document_content],
            ids=[doc_id],
            metadata=[metadata]
        )
        
        return doc_id
    
    async def _store_json_reference(self, session: Session, project_id: str, json_type: str, 
                                   chroma_document_id: str, json_content: Dict[str, Any], 
                                   updated_by: str, update_reason: str) -> None:
        """Store JSON reference in PostgreSQL"""
        # Deactivate existing record if exists
        await session.execute(
            select(ProjectJSONStore).where(
                ProjectJSONStore.project_id == project_id,
                ProjectJSONStore.json_type == json_type,
                ProjectJSONStore.is_active == True
            )
        )
        existing_record = session.execute(
            select(ProjectJSONStore).where(
                ProjectJSONStore.project_id == project_id,
                ProjectJSONStore.json_type == json_type,
                ProjectJSONStore.is_active == True
            )
        ).scalar_one_or_none()
        
        if existing_record:
            existing_record.is_active = False
            existing_record.updated_at = datetime.utcnow()
        
        # Create new record
        new_record = ProjectJSONStore(
            project_id=project_id,
            chroma_document_id=chroma_document_id,
            json_type=json_type,
            json_content=json_content,
            last_updated_by=updated_by,
            update_reason=update_reason
        )
        
        session.add(new_record)
        await session.commit() 