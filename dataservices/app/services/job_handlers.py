"""
Job Handlers for Project JSON Schemas Processing
Handles the actual processing of different job types
"""

import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.services.job_queue_service import JobData, JobType
from app.services.project_json_service import ProjectJSONService
from app.service.post_commit_service import PostCommitService
from app.core.session_manager import SessionManager
from app.utils.history import ProjectManager
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class JobHandlers:
    """Job handlers for different job types"""
    
    def __init__(self):
        self.settings = get_settings()
        self.session_manager = SessionManager.get_instance()
        self.project_manager = ProjectManager(None)
        self.json_service = ProjectJSONService(self.session_manager, self.project_manager)
    
    async def handle_project_json_tables(self, job_data: JobData) -> Dict[str, Any]:
        """Handle project JSON tables job"""
        logger.info(f"Processing project JSON tables job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Store tables JSON
            chroma_doc_id = await self.json_service.store_project_tables_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            
            result = {
                "job_id": job_data.job_id,
                "project_id": job_data.project_id,
                "job_type": job_data.job_type.value,
                "chroma_document_id": chroma_doc_id,
                "status": "completed",
                "message": "Tables JSON stored successfully"
            }
            
            logger.info(f"Completed project JSON tables job {job_data.job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed project JSON tables job {job_data.job_id}: {str(e)}")
            raise
    
    async def handle_project_json_metrics(self, job_data: JobData) -> Dict[str, Any]:
        """Handle project JSON metrics job"""
        logger.info(f"Processing project JSON metrics job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Store metrics JSON
            chroma_doc_id = await self.json_service.store_project_metrics_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            
            result = {
                "job_id": job_data.job_id,
                "project_id": job_data.project_id,
                "job_type": job_data.job_type.value,
                "chroma_document_id": chroma_doc_id,
                "status": "completed",
                "message": "Metrics JSON stored successfully"
            }
            
            logger.info(f"Completed project JSON metrics job {job_data.job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed project JSON metrics job {job_data.job_id}: {str(e)}")
            raise
    
    async def handle_project_json_views(self, job_data: JobData) -> Dict[str, Any]:
        """Handle project JSON views job"""
        logger.info(f"Processing project JSON views job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Store views JSON
            chroma_doc_id = await self.json_service.store_project_views_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            
            result = {
                "job_id": job_data.job_id,
                "project_id": job_data.project_id,
                "job_type": job_data.job_type.value,
                "chroma_document_id": chroma_doc_id,
                "status": "completed",
                "message": "Views JSON stored successfully"
            }
            
            logger.info(f"Completed project JSON views job {job_data.job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed project JSON views job {job_data.job_id}: {str(e)}")
            raise
    
    async def handle_project_json_calculated_columns(self, job_data: JobData) -> Dict[str, Any]:
        """Handle project JSON calculated columns job"""
        logger.info(f"Processing project JSON calculated columns job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Store calculated columns JSON
            chroma_doc_id = await self.json_service.store_project_calculated_columns_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            
            result = {
                "job_id": job_data.job_id,
                "project_id": job_data.project_id,
                "job_type": job_data.job_type.value,
                "chroma_document_id": chroma_doc_id,
                "status": "completed",
                "message": "Calculated columns JSON stored successfully"
            }
            
            logger.info(f"Completed project JSON calculated columns job {job_data.job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed project JSON calculated columns job {job_data.job_id}: {str(e)}")
            raise
    
    async def handle_project_json_summary(self, job_data: JobData) -> Dict[str, Any]:
        """Handle project JSON summary job"""
        logger.info(f"Processing project JSON summary job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Store project summary JSON
            chroma_doc_id = await self.json_service.store_project_summary_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            
            result = {
                "job_id": job_data.job_id,
                "project_id": job_data.project_id,
                "job_type": job_data.job_type.value,
                "chroma_document_id": chroma_doc_id,
                "status": "completed",
                "message": "Project summary JSON stored successfully"
            }
            
            logger.info(f"Completed project JSON summary job {job_data.job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed project JSON summary job {job_data.job_id}: {str(e)}")
            raise
    
    async def handle_project_json_all(self, job_data: JobData) -> Dict[str, Any]:
        """Handle project JSON all types job"""
        logger.info(f"Processing project JSON all types job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Store all JSON types
            tables_doc_id = await self.json_service.store_project_tables_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            metrics_doc_id = await self.json_service.store_project_metrics_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            views_doc_id = await self.json_service.store_project_views_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            calc_columns_doc_id = await self.json_service.store_project_calculated_columns_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            summary_doc_id = await self.json_service.store_project_summary_json(
                job_data.project_id, 
                job_data.user_id or 'system'
            )
            
            result = {
                "job_id": job_data.job_id,
                "project_id": job_data.project_id,
                "job_type": job_data.job_type.value,
                "chroma_document_ids": {
                    "tables": tables_doc_id,
                    "metrics": metrics_doc_id,
                    "views": views_doc_id,
                    "calculated_columns": calc_columns_doc_id,
                    "summary": summary_doc_id
                },
                "status": "completed",
                "message": "All project JSON types stored successfully"
            }
            
            logger.info(f"Completed project JSON all types job {job_data.job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed project JSON all types job {job_data.job_id}: {str(e)}")
            raise
    
    async def handle_chromadb_indexing(self, job_data: JobData) -> Dict[str, Any]:
        """Handle ChromaDB indexing job using MDL data from LLM definition generation"""
        logger.info(f"Processing ChromaDB indexing job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Import indexing components
            from app.indexing.project_meta import ProjectMeta
            from app.indexing.table_description import TableDescription
            from app.indexing.db_schema import DBSchema
            from app.storage.documents import DocumentChromaStore
            from app.core.dependencies import get_doc_store_provider
            from langchain_openai import OpenAIEmbeddings
            from datetime import datetime
            
            # Get project details from database
            async with self.session_manager.get_async_db_session() as db:
                from app.schemas.dbmodels import Project
                from sqlalchemy import select
                
                result = await db.execute(
                    select(Project).where(Project.project_id == job_data.project_id)
                )
                project = result.scalar_one_or_none()
                
                if not project:
                    raise ValueError(f"Project {job_data.project_id} not found")
                
                # Get project metadata
                project_metadata = project.json_metadata or {}
                llm_definitions = project_metadata.get("llm_definitions", {})
                mdl_file_path = llm_definitions.get("mdl_file_path")
                
                if not mdl_file_path:
                    raise ValueError(f"No MDL file path found for project {job_data.project_id}")
                
                # Read MDL file
                import json
                import os
                
                if not os.path.exists(mdl_file_path):
                    raise FileNotFoundError(f"MDL file not found: {mdl_file_path}")
                
                with open(mdl_file_path, 'r', encoding='utf-8') as f:
                    mdl_data = json.load(f)
                
                # Initialize embeddings
                embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    openai_api_key=self.settings.OPENAI_API_KEY
                )
                
                # Get document stores
                doc_store_provider = get_doc_store_provider()
                document_stores = doc_store_provider.stores
                
                # Initialize indexing components
                project_meta_processor = ProjectMeta(
                    document_store=document_stores["project_meta"]
                )
                
                table_description_processor = TableDescription(
                    document_store=document_stores["table_description"],
                    embedder=embeddings
                )
                
                db_schema_processor = DBSchema(
                    document_store=document_stores["db_schema"],
                    embedder=embeddings
                )
                
                # Process project metadata
                logger.info("Processing project metadata")
                project_meta_result = await project_meta_processor.run(
                    mdl_str=json.dumps(mdl_data),
                    project_id=job_data.project_id
                )
                
                # Process table descriptions
                logger.info("Processing table descriptions")
                table_description_result = await table_description_processor.run(
                    mdl=json.dumps(mdl_data),
                    project_id=job_data.project_id
                )
                
                # Process database schema
                logger.info("Processing database schema")
                db_schema_result = await db_schema_processor.run(
                    mdl_str=json.dumps(mdl_data),
                    project_id=job_data.project_id
                )
                
                # Compile results
                indexing_results = {
                    "project_meta": project_meta_result,
                    "table_description": table_description_result,
                    "db_schema": db_schema_result
                }
                
                # Update project metadata with indexing results
                project.json_metadata = project.json_metadata or {}
                project.json_metadata["chromadb_indexing"] = {
                    "indexed_at": datetime.utcnow().isoformat(),
                    "indexed_by": job_data.user_id or 'system',
                    "results": indexing_results,
                    "mdl_file_path": mdl_file_path
                }
                
                await db.commit()
                
                result = {
                    "job_id": job_data.job_id,
                    "project_id": job_data.project_id,
                    "job_type": job_data.job_type.value,
                    "indexing_results": indexing_results,
                    "status": "completed",
                    "message": "ChromaDB indexing completed successfully"
                }
                
                logger.info(f"Completed ChromaDB indexing job {job_data.job_id}")
                return result
                
        except Exception as e:
            logger.error(f"Failed ChromaDB indexing job {job_data.job_id}: {str(e)}")
            raise
    
    async def handle_post_commit_workflow(self, job_data: JobData) -> Dict[str, Any]:
        """Handle post-commit workflow job"""
        logger.info(f"Processing post-commit workflow job {job_data.job_id} for project {job_data.project_id}")
        
        try:
            # Create post-commit service
            post_commit_service = PostCommitService(
                job_data.user_id or 'system', 
                job_data.session_id or 'system'
            )
            
            # Execute post-commit workflows
            async with self.session_manager.get_async_db_session() as db:
                results = await post_commit_service.execute_post_commit_workflows(
                    job_data.project_id, 
                    db
                )
            
            result = {
                "job_id": job_data.job_id,
                "project_id": job_data.project_id,
                "job_type": job_data.job_type.value,
                "workflow_results": results,
                "status": "completed",
                "message": "Post-commit workflow completed successfully"
            }
            
            logger.info(f"Completed post-commit workflow job {job_data.job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed post-commit workflow job {job_data.job_id}: {str(e)}")
            raise


# Global job handlers instance
job_handlers = JobHandlers()


def register_job_handlers(job_queue_service):
    """Register all job handlers with the job queue service"""
    from app.services.job_queue_service import JobType
    
    # Register handlers for each job type
    job_queue_service.register_handler(JobType.PROJECT_JSON_TABLES, job_handlers.handle_project_json_tables)
    job_queue_service.register_handler(JobType.PROJECT_JSON_METRICS, job_handlers.handle_project_json_metrics)
    job_queue_service.register_handler(JobType.PROJECT_JSON_VIEWS, job_handlers.handle_project_json_views)
    job_queue_service.register_handler(JobType.PROJECT_JSON_CALCULATED_COLUMNS, job_handlers.handle_project_json_calculated_columns)
    job_queue_service.register_handler(JobType.PROJECT_JSON_SUMMARY, job_handlers.handle_project_json_summary)
    job_queue_service.register_handler(JobType.PROJECT_JSON_ALL, job_handlers.handle_project_json_all)
    job_queue_service.register_handler(JobType.CHROMADB_INDEXING, job_handlers.handle_chromadb_indexing)
    job_queue_service.register_handler(JobType.POST_COMMIT_WORKFLOW, job_handlers.handle_post_commit_workflow)
    
    logger.info("Registered all job handlers") 