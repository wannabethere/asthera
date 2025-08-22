"""
Report Writing Service

This service integrates the report writing agent with the existing workflow system,
providing a clean API for report generation with self-correcting RAG capabilities.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_async_db_session
from app.models.workflowmodels import ReportWorkflow, ThreadComponent
from app.models.dbmodels import Report
from app.agents.report_writing_agent import (
    ReportWritingAgent,
    WriterActorType,
    BusinessGoal,
    create_report_writing_agent
)

logger = logging.getLogger(__name__)


class ReportWritingService:
    """Service for managing report writing operations"""
    
    def __init__(self, db: AsyncSession = Depends(get_async_db_session)):
        self.db = db
        self.agent = create_report_writing_agent()
    
    def generate_report_with_agent(
        self,
        workflow_id: UUID,
        writer_actor: WriterActorType,
        business_goal: BusinessGoal,
        user_id: UUID
    ) -> Dict[str, Any]:
        """Generate report using the AI agent with self-correcting RAG"""
        
        try:
            # Validate workflow access
            workflow = self._validate_workflow_access(workflow_id, user_id)
            
            # Validate thread components exist
            thread_components = self._get_thread_components(workflow_id)
            if not thread_components:
                raise HTTPException(
                    status_code=400,
                    detail="No thread components found for report generation"
                )
            
            # Generate report using agent
            report_result = self.agent.generate_report(
                workflow_id=workflow_id,
                writer_actor=writer_actor,
                business_goal=business_goal
            )
            
            # Store generation metadata
            self._store_generation_metadata(workflow_id, report_result, user_id)
            
            # Update workflow state
            workflow.workflow_metadata = workflow.workflow_metadata or {}
            workflow.workflow_metadata.update({
                "last_report_generation": {
                    "timestamp": datetime.now().isoformat(),
                    "writer_actor": writer_actor.value,
                    "business_goal": business_goal.dict(),
                    "quality_score": report_result.get("quality_assessment", {}).get("average_quality_score", 0.0),
                    "iterations": report_result.get("generation_metadata", {}).get("iterations", 0)
                }
            })
            
            self.db.commit()
            
            return {
                "success": True,
                "workflow_id": str(workflow_id),
                "report_data": report_result,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate report: {str(e)}"
            )
    
    def get_report_generation_status(
        self,
        workflow_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """Get the status of report generation for a workflow"""
        
        workflow = self._validate_workflow_access(workflow_id, user_id)
        
        metadata = workflow.workflow_metadata or {}
        generation_info = metadata.get("last_report_generation", {})
        
        return {
            "workflow_id": str(workflow_id),
            "has_generated_report": bool(generation_info),
            "last_generation": generation_info.get("timestamp"),
            "writer_actor": generation_info.get("writer_actor"),
            "quality_score": generation_info.get("quality_score"),
            "iterations": generation_info.get("iterations"),
            "business_goal": generation_info.get("business_goal")
        }
    
    def regenerate_report_with_feedback(
        self,
        workflow_id: UUID,
        user_id: UUID,
        feedback: Dict[str, Any],
        writer_actor: Optional[WriterActorType] = None,
        business_goal: Optional[BusinessGoal] = None
    ) -> Dict[str, Any]:
        """Regenerate report based on user feedback"""
        
        try:
            workflow = self._validate_workflow_access(workflow_id, user_id)
            
            # Get current generation metadata
            metadata = workflow.workflow_metadata or {}
            last_generation = metadata.get("last_report_generation", {})
            
            # Use existing settings if not provided
            if not writer_actor:
                writer_actor = WriterActorType(last_generation.get("writer_actor", "analyst"))
            
            if not business_goal:
                business_goal = BusinessGoal(**last_generation.get("business_goal", {}))
            
            # Update business goal with feedback
            if feedback.get("business_objective"):
                business_goal.primary_objective = feedback["business_objective"]
            if feedback.get("target_audience"):
                business_goal.target_audience = feedback["target_audience"]
            if feedback.get("decision_context"):
                business_goal.decision_context = feedback["decision_context"]
            
            # Regenerate report
            report_result = self.agent.generate_report(
                workflow_id=workflow_id,
                writer_actor=writer_actor,
                business_goal=business_goal
            )
            
            # Store regeneration metadata
            self._store_generation_metadata(workflow_id, report_result, user_id, is_regeneration=True)
            
            # Update workflow metadata
            workflow.workflow_metadata.update({
                "last_report_generation": {
                    "timestamp": datetime.now().isoformat(),
                    "writer_actor": writer_actor.value,
                    "business_goal": business_goal.dict(),
                    "quality_score": report_result.get("quality_assessment", {}).get("average_quality_score", 0.0),
                    "iterations": report_result.get("generation_metadata", {}).get("iterations", 0),
                    "is_regeneration": True,
                    "feedback_applied": feedback
                }
            })
            
            self.db.commit()
            
            return {
                "success": True,
                "workflow_id": str(workflow_id),
                "report_data": report_result,
                "regenerated_at": datetime.now().isoformat(),
                "feedback_applied": feedback
            }
            
        except Exception as e:
            logger.error(f"Error regenerating report: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to regenerate report: {str(e)}"
            )
    
    def get_available_writer_actors(self) -> List[Dict[str, str]]:
        """Get available writer actor types with descriptions"""
        return [
            {
                "value": WriterActorType.EXECUTIVE.value,
                "label": "Executive",
                "description": "High-level strategic reports for C-suite and executives"
            },
            {
                "value": WriterActorType.ANALYST.value,
                "label": "Analyst",
                "description": "Detailed analytical reports for business analysts"
            },
            {
                "value": WriterActorType.TECHNICAL.value,
                "label": "Technical",
                "description": "Technical reports for IT and engineering teams"
            },
            {
                "value": WriterActorType.BUSINESS_USER.value,
                "label": "Business User",
                "description": "User-friendly reports for business stakeholders"
            },
            {
                "value": WriterActorType.DATA_SCIENTIST.value,
                "label": "Data Scientist",
                "description": "Advanced analytical reports with statistical insights"
            },
            {
                "value": WriterActorType.CONSULTANT.value,
                "label": "Consultant",
                "description": "Professional consulting reports for external stakeholders"
            }
        ]
    
    def get_report_quality_metrics(
        self,
        workflow_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """Get detailed quality metrics for the generated report"""
        
        workflow = self._validate_workflow_access(workflow_id, user_id)
        metadata = workflow.workflow_metadata or {}
        generation_info = metadata.get("last_report_generation", {})
        
        if not generation_info:
            raise HTTPException(
                status_code=404,
                detail="No report generation found for this workflow"
            )
        
        return {
            "workflow_id": str(workflow_id),
            "quality_score": generation_info.get("quality_score", 0.0),
            "iterations": generation_info.get("iterations", 0),
            "writer_actor": generation_info.get("writer_actor"),
            "business_goal_alignment": generation_info.get("business_goal", {}),
            "generation_timestamp": generation_info.get("timestamp"),
            "is_regeneration": generation_info.get("is_regeneration", False)
        }
    
    def _validate_workflow_access(self, workflow_id: UUID, user_id: UUID) -> ReportWorkflow:
        """Validate that user has access to the workflow"""
        
        workflow = self.db.query(ReportWorkflow).filter(
            ReportWorkflow.id == workflow_id,
            ReportWorkflow.user_id == user_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail="Workflow not found or access denied"
            )
        
        return workflow
    
    def _get_thread_components(self, workflow_id: UUID) -> List[ThreadComponent]:
        """Get thread components for a workflow"""
        
        return self.db.query(ThreadComponent).filter(
            ThreadComponent.report_workflow_id == workflow_id
        ).order_by(ThreadComponent.sequence_order).all()
    
    def _store_generation_metadata(
        self,
        workflow_id: UUID,
        report_result: Dict[str, Any],
        user_id: UUID,
        is_regeneration: bool = False
    ) -> None:
        """Store metadata about report generation"""
        
        # This could be extended to store in a separate table
        # For now, we're storing in workflow metadata
        logger.info(f"Storing generation metadata for workflow {workflow_id}")
        
        # You could also store the full report result in a separate table
        # if you want to maintain a history of all generated reports
    
    def export_report_to_format(
        self,
        workflow_id: UUID,
        user_id: UUID,
        format_type: str = "json"
    ) -> Dict[str, Any]:
        """Export the generated report to a specific format"""
        
        workflow = self._validate_workflow_access(workflow_id, user_id)
        metadata = workflow.workflow_metadata or {}
        generation_info = metadata.get("last_report_generation", {})
        
        if not generation_info:
            raise HTTPException(
                status_code=404,
                detail="No report generation found for this workflow"
            )
        
        # For now, return the stored metadata
        # This could be extended to format the report in different ways
        if format_type == "json":
            return {
                "workflow_id": str(workflow_id),
                "report_metadata": generation_info,
                "export_format": format_type,
                "exported_at": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported export format: {format_type}"
            )


# Dependency injection helper
def get_report_writing_service(db: Session = Depends(get_db)) -> ReportWritingService:
    """Get report writing service instance"""
    return ReportWritingService(db)
