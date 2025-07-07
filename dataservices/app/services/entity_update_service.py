"""
Entity Update Service
Automatically submits jobs to the queue when entities are updated
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.job_queue_service import job_queue_service, JobType
from app.services.job_handlers import register_job_handlers

logger = logging.getLogger(__name__)


class EntityUpdateService:
    """Service for handling entity updates and job submission"""
    
    def __init__(self):
        self.job_queue = job_queue_service
        # Register job handlers
        register_job_handlers(self.job_queue)
    
    async def on_table_updated(
        self,
        project_id: str,
        table_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Handle table update - submit jobs for tables and summary"""
        logger.info(f"Table updated: {table_id} in project {project_id}")
        
        try:
            # Submit tables JSON job
            tables_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_TABLES,
                project_id=project_id,
                entity_type="table",
                entity_id=table_id,
                user_id=user_id,
                session_id=session_id,
                priority=1,  # High priority for table updates
                metadata={
                    "update_type": "table_updated",
                    "table_id": table_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            # Submit summary job (lower priority)
            summary_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_SUMMARY,
                project_id=project_id,
                entity_type="table",
                entity_id=table_id,
                user_id=user_id,
                session_id=session_id,
                priority=2,  # Lower priority for summary
                metadata={
                    "update_type": "table_updated",
                    "table_id": table_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            logger.info(f"Submitted jobs for table update: tables={tables_job_id}, summary={summary_job_id}")
            
            return {
                "tables_job_id": tables_job_id,
                "summary_job_id": summary_job_id
            }
            
        except Exception as e:
            logger.error(f"Failed to submit jobs for table update {table_id}: {str(e)}")
            raise
    
    async def on_column_updated(
        self,
        project_id: str,
        table_id: str,
        column_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Handle column update - submit jobs for tables and summary"""
        logger.info(f"Column updated: {column_id} in table {table_id}, project {project_id}")
        
        try:
            # Submit tables JSON job (includes columns)
            tables_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_TABLES,
                project_id=project_id,
                entity_type="column",
                entity_id=column_id,
                user_id=user_id,
                session_id=session_id,
                priority=1,
                metadata={
                    "update_type": "column_updated",
                    "table_id": table_id,
                    "column_id": column_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            # Submit summary job
            summary_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_SUMMARY,
                project_id=project_id,
                entity_type="column",
                entity_id=column_id,
                user_id=user_id,
                session_id=session_id,
                priority=2,
                metadata={
                    "update_type": "column_updated",
                    "table_id": table_id,
                    "column_id": column_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            logger.info(f"Submitted jobs for column update: tables={tables_job_id}, summary={summary_job_id}")
            
            return {
                "tables_job_id": tables_job_id,
                "summary_job_id": summary_job_id
            }
            
        except Exception as e:
            logger.error(f"Failed to submit jobs for column update {column_id}: {str(e)}")
            raise
    
    async def on_metric_updated(
        self,
        project_id: str,
        metric_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Handle metric update - submit jobs for metrics and summary"""
        logger.info(f"Metric updated: {metric_id} in project {project_id}")
        
        try:
            # Submit metrics JSON job
            metrics_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_METRICS,
                project_id=project_id,
                entity_type="metric",
                entity_id=metric_id,
                user_id=user_id,
                session_id=session_id,
                priority=1,
                metadata={
                    "update_type": "metric_updated",
                    "metric_id": metric_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            # Submit summary job
            summary_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_SUMMARY,
                project_id=project_id,
                entity_type="metric",
                entity_id=metric_id,
                user_id=user_id,
                session_id=session_id,
                priority=2,
                metadata={
                    "update_type": "metric_updated",
                    "metric_id": metric_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            logger.info(f"Submitted jobs for metric update: metrics={metrics_job_id}, summary={summary_job_id}")
            
            return {
                "metrics_job_id": metrics_job_id,
                "summary_job_id": summary_job_id
            }
            
        except Exception as e:
            logger.error(f"Failed to submit jobs for metric update {metric_id}: {str(e)}")
            raise
    
    async def on_view_updated(
        self,
        project_id: str,
        view_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Handle view update - submit jobs for views and summary"""
        logger.info(f"View updated: {view_id} in project {project_id}")
        
        try:
            # Submit views JSON job
            views_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_VIEWS,
                project_id=project_id,
                entity_type="view",
                entity_id=view_id,
                user_id=user_id,
                session_id=session_id,
                priority=1,
                metadata={
                    "update_type": "view_updated",
                    "view_id": view_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            # Submit summary job
            summary_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_SUMMARY,
                project_id=project_id,
                entity_type="view",
                entity_id=view_id,
                user_id=user_id,
                session_id=session_id,
                priority=2,
                metadata={
                    "update_type": "view_updated",
                    "view_id": view_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            logger.info(f"Submitted jobs for view update: views={views_job_id}, summary={summary_job_id}")
            
            return {
                "views_job_id": views_job_id,
                "summary_job_id": summary_job_id
            }
            
        except Exception as e:
            logger.error(f"Failed to submit jobs for view update {view_id}: {str(e)}")
            raise
    
    async def on_calculated_column_updated(
        self,
        project_id: str,
        calculated_column_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Handle calculated column update - submit jobs for calculated columns and summary"""
        logger.info(f"Calculated column updated: {calculated_column_id} in project {project_id}")
        
        try:
            # Submit calculated columns JSON job
            calc_columns_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_CALCULATED_COLUMNS,
                project_id=project_id,
                entity_type="calculated_column",
                entity_id=calculated_column_id,
                user_id=user_id,
                session_id=session_id,
                priority=1,
                metadata={
                    "update_type": "calculated_column_updated",
                    "calculated_column_id": calculated_column_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            # Submit summary job
            summary_job_id = await self.job_queue.submit_job(
                job_type=JobType.PROJECT_JSON_SUMMARY,
                project_id=project_id,
                entity_type="calculated_column",
                entity_id=calculated_column_id,
                user_id=user_id,
                session_id=session_id,
                priority=2,
                metadata={
                    "update_type": "calculated_column_updated",
                    "calculated_column_id": calculated_column_id,
                    "updated_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            logger.info(f"Submitted jobs for calculated column update: calculated_columns={calc_columns_job_id}, summary={summary_job_id}")
            
            return {
                "calculated_columns_job_id": calc_columns_job_id,
                "summary_job_id": summary_job_id
            }
            
        except Exception as e:
            logger.error(f"Failed to submit jobs for calculated column update {calculated_column_id}: {str(e)}")
            raise
    
    async def on_project_committed(
        self,
        project_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Handle project commit - submit post-commit workflow and ChromaDB indexing jobs"""
        logger.info(f"Project committed: {project_id}")
        
        try:
            # Submit post-commit workflow job (highest priority)
            workflow_job_id = await self.job_queue.submit_job(
                job_type=JobType.POST_COMMIT_WORKFLOW,
                project_id=project_id,
                entity_type="project",
                entity_id=project_id,
                user_id=user_id,
                session_id=session_id,
                priority=0,  # Highest priority for project commits
                metadata={
                    "update_type": "project_committed",
                    "committed_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            # Submit ChromaDB indexing job (medium priority)
            indexing_job_id = await self.job_queue.submit_job(
                job_type=JobType.CHROMADB_INDEXING,
                project_id=project_id,
                entity_type="project",
                entity_id=project_id,
                user_id=user_id,
                session_id=session_id,
                priority=1,  # Medium priority for indexing
                metadata={
                    "update_type": "project_committed",
                    "committed_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            
            logger.info(f"Submitted post-commit workflow job: {workflow_job_id}")
            logger.info(f"Submitted ChromaDB indexing job: {indexing_job_id}")
            
            return {
                "workflow_job_id": workflow_job_id,
                "indexing_job_id": indexing_job_id
            }
            
        except Exception as e:
            logger.error(f"Failed to submit project commit jobs for project {project_id}: {str(e)}")
            raise
    
    async def on_bulk_update(
        self,
        project_id: str,
        entity_updates: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Handle bulk entity updates - submit all jobs at once"""
        logger.info(f"Bulk update for project {project_id}: {len(entity_updates)} entities")
        
        try:
            job_ids = []
            
            # Submit jobs for each entity update
            for update in entity_updates:
                entity_type = update.get("entity_type")
                entity_id = update.get("entity_id")
                
                if entity_type == "table":
                    result = await self.on_table_updated(
                        project_id, entity_id, user_id, session_id, metadata
                    )
                    job_ids.extend([result["tables_job_id"], result["summary_job_id"]])
                elif entity_type == "column":
                    table_id = update.get("table_id")
                    result = await self.on_column_updated(
                        project_id, table_id, entity_id, user_id, session_id, metadata
                    )
                    job_ids.extend([result["tables_job_id"], result["summary_job_id"]])
                elif entity_type == "metric":
                    result = await self.on_metric_updated(
                        project_id, entity_id, user_id, session_id, metadata
                    )
                    job_ids.extend([result["metrics_job_id"], result["summary_job_id"]])
                elif entity_type == "view":
                    result = await self.on_view_updated(
                        project_id, entity_id, user_id, session_id, metadata
                    )
                    job_ids.extend([result["views_job_id"], result["summary_job_id"]])
                elif entity_type == "calculated_column":
                    result = await self.on_calculated_column_updated(
                        project_id, entity_id, user_id, session_id, metadata
                    )
                    job_ids.extend([result["calculated_columns_job_id"], result["summary_job_id"]])
            
            logger.info(f"Submitted {len(job_ids)} jobs for bulk update")
            
            return {
                "job_ids": job_ids,
                "total_jobs": len(job_ids)
            }
            
        except Exception as e:
            logger.error(f"Failed to submit jobs for bulk update in project {project_id}: {str(e)}")
            raise
    
    async def start_worker(self):
        """Start the job queue worker"""
        await self.job_queue.start_worker()
        logger.info("Entity update service worker started")
    
    async def stop_worker(self):
        """Stop the job queue worker"""
        await self.job_queue.stop_worker()
        logger.info("Entity update service worker stopped")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return await self.job_queue.get_queue_stats()


# Global entity update service instance
entity_update_service = EntityUpdateService() 