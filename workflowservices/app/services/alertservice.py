from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, select
from sqlalchemy.orm import selectinload
from app.services.baseservice import BaseService, SharingPermission
from app.models.dbmodels import (
    Task, Dataset, Metric, Condition, Alert, UpdateAction, MetricType
)
from app.models.thread import Thread, Workflow
from app.models.workspace import Workspace, Project
from app.models.schema import (
    TaskCreate, TaskUpdate, DatasetDetails, MetricDetails, 
    ConditionDetails, AlertResponse
)

class AlertService(BaseService):
    """Service for managing alerts, tasks, and conditions"""
    
    def __init__(self, db: AsyncSession, chroma_client=None):
        super().__init__(db, chroma_client)
        self.collection_name = "alerts"
        self.task_collection = "tasks"
    
    async def create_task(
        self,
        user_id: UUID,
        task_data: TaskCreate,
        workflow_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None
    ) -> Task:
        """Create a new task with datasets, metrics, and conditions"""
        
        # Check permissions
        if project_id and not await self._check_user_permission(
            user_id, "project", project_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create task in this project")
        
        if workspace_id and not await self._check_user_permission(
            user_id, "workspace", workspace_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create task in this workspace")
        
        # Validate workflow if provided
        if workflow_id:
            stmt = select(Workflow).where(Workflow.id == workflow_id)
            result = await self.db.execute(stmt)
            workflow = result.scalar_one_or_none()
            
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
            if workflow.user_id != user_id and not await self._check_user_permission(
                user_id, "thread", workflow.thread_id, "read"
            ):
                raise PermissionError("User doesn't have access to this workflow")
        
        # Create task
        task = Task(
            name=task_data.name,
            description=task_data.description,
            status=task_data.status or "active"
        )
        
        self.db.add(task)
        await self.db.flush()
        
        # Create datasets
        datasets = task_data.dataset_details
        if not isinstance(datasets, list):
            datasets = [datasets]
        
        for dataset_data in datasets:
            dataset = await self._create_dataset(task.id, dataset_data)
            self.db.add(dataset)
        
        # Create metrics
        metrics = task_data.metric_details
        if not isinstance(metrics, list):
            metrics = [metrics]
        
        for metric_data in metrics:
            metric = await self._create_metric(task.id, metric_data)
            self.db.add(metric)
        
        # Create conditions and alerts
        conditions = task_data.condition_details
        if not isinstance(conditions, list):
            conditions = [conditions]
        
        for condition_data in conditions:
            condition = await self._create_condition(task.id, condition_data, project_id)
            self.db.add(condition)
        
        # Store in ChromaDB for searchability
        metadata = {
            "created_by": str(user_id),
            "workflow_id": str(workflow_id) if workflow_id else None,
            "project_id": str(project_id) if project_id else None,
            "workspace_id": str(workspace_id) if workspace_id else None,
            "status": task.status
        }
        
        await self._add_to_chroma(
            self.task_collection,
            str(task.id),
            {
                "name": task.name,
                "description": task.description,
                "status": task.status,
                "dataset_count": len(datasets),
                "metric_count": len(metrics),
                "condition_count": len(conditions)
            },
            metadata
        )
        
        await self.db.commit()
        return task
    
    async def get_task(
        self,
        user_id: UUID,
        task_id: UUID
    ) -> Optional[Task]:
        """Get task by ID with permission check"""
        
        stmt = select(Task).where(Task.id == task_id)
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            return None
        
        # Check permissions via ChromaDB metadata
        collection = await self._create_chroma_collection(self.task_collection)
        result = await collection.get(ids=[str(task_id)])
        
        if not result["ids"]:
            return None
        
        metadata = result["metadatas"][0]
        
        # Check if user has access
        if not await self._has_task_access(user_id, metadata):
            raise PermissionError("User doesn't have access to this task")
        
        return task
    
    async def update_task(
        self,
        user_id: UUID,
        task_id: UUID,
        update_data: TaskUpdate
    ) -> Task:
        """Update task and its components"""
        
        task = await self.get_task(user_id, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Check update permission
        collection = await self._create_chroma_collection(self.task_collection)
        result = await collection.get(ids=[str(task_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not await self._check_user_permission(
            user_id, "task", task_id, "update"
        ):
            raise PermissionError("User doesn't have permission to update this task")
        
        # Update task fields
        if update_data.name:
            task.name = update_data.name
        if update_data.description:
            task.description = update_data.description
        if update_data.status:
            task.status = update_data.status
        
        # Update dataset if provided
        if update_data.dataset_details:
            # For simplicity, update the first dataset
            if task.datasets:
                await self._update_dataset(task.datasets[0], update_data.dataset_details)
        
        # Update metric if provided
        if update_data.metric_details:
            # For simplicity, update the first metric
            if task.metrics:
                await self._update_metric(task.metrics[0], update_data.metric_details)
        
        # Update condition if provided
        if update_data.condition_details:
            # For simplicity, update the first condition
            if task.conditions:
                await self._update_condition(task.conditions[0], update_data.condition_details)
        
        task.updated_at = datetime.utcnow()
        
        # Update ChromaDB
        await self._update_chroma(
            self.task_collection,
            str(task_id),
            {
                "name": task.name,
                "description": task.description,
                "status": task.status,
                "dataset_count": len(task.datasets),
                "metric_count": len(task.metrics),
                "condition_count": len(task.conditions)
            },
            metadata
        )
        
        await self.db.commit()
        return task
    
    async def delete_task(
        self,
        user_id: UUID,
        task_id: UUID
    ) -> bool:
        """Delete task and all its components"""
        
        task = await self.get_task(user_id, task_id)
        if not task:
            return False
        
        # Check delete permission
        collection = await self._create_chroma_collection(self.task_collection)
        result = await collection.get(ids=[str(task_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not await self._check_user_permission(
            user_id, "task", task_id, "delete"
        ):
            raise PermissionError("User doesn't have permission to delete this task")
        
        # Delete from ChromaDB
        await self._delete_from_chroma(self.task_collection, str(task_id))
        
        # Delete alerts from ChromaDB
        for condition in task.conditions:
            if condition.alert:
                await self._delete_from_chroma(self.collection_name, str(condition.alert.id))
        
        # Delete from PostgreSQL (cascades will handle related entities)
        await self.db.delete(task)
        await self.db.commit()
        
        return True
    
    async def search_tasks(
        self,
        user_id: UUID,
        query: str,
        workspace_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search tasks with permission filtering"""
        
        # Build filters
        filters = {}
        if workspace_id:
            filters["workspace_id"] = str(workspace_id)
        if project_id:
            filters["project_id"] = str(project_id)
        if status:
            filters["status"] = status
        
        # Search in ChromaDB
        results = await self._search_chroma(
            self.task_collection,
            query,
            filters,
            limit * 2
        )
        
        # Filter by permissions
        accessible_results = []
        for result in results:
            if await self._has_task_access(user_id, result["metadata"]):
                task_id = UUID(result["id"])
                stmt = select(Task).where(Task.id == task_id)
                result_obj = await self.db.execute(stmt)
                task = result_obj.scalar_one_or_none()
                
                if task:
                    accessible_results.append({
                        "task": task,
                        "metadata": result["metadata"],
                        "relevance_score": 1 - result["distance"] if result["distance"] else 1
                    })
                    if len(accessible_results) >= limit:
                        break
        
        return accessible_results
    
    async def get_active_alerts(
        self,
        user_id: UUID,
        project_id: Optional[UUID] = None,
        notification_group: Optional[str] = None
    ) -> List[Alert]:
        """Get active alerts for user"""
        
        stmt = select(Alert).join(
            Condition, Alert.condition_id == Condition.id
        ).join(
            Task, Condition.task_id == Task.id
        ).where(
            Task.status == "active"
        )
        
        if project_id:
            stmt = stmt.where(Alert.project_id == str(project_id))
        
        if notification_group:
            stmt = stmt.where(Alert.notification_group == notification_group)
        
        result = await self.db.execute(stmt)
        alerts = result.scalars().all()
        
        # Filter by user access
        accessible_alerts = []
        for alert in alerts:
            # Get task metadata from ChromaDB
            collection = await self._create_chroma_collection(self.task_collection)
            result = await collection.get(ids=[str(alert.condition.task_id)])
            if result["ids"]:
                metadata = result["metadatas"][0]
                if await self._has_task_access(user_id, metadata):
                    accessible_alerts.append(alert)
        
        return accessible_alerts
    
    async def trigger_alert(
        self,
        alert_id: UUID,
        triggered_by: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger an alert and return notification details"""
        
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await self.db.execute(stmt)
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")
        
        # Get condition and metric details
        condition = alert.condition
        task = condition.task
        
        # Create alert notification
        notification = {
            "alert_id": str(alert.id),
            "task_name": task.name,
            "condition_name": condition.name,
            "metric_name": condition.metric_name,
            "triggered_at": datetime.utcnow().isoformat(),
            "triggered_by": triggered_by,
            "notification_group": alert.notification_group,
            "comparison": condition.comparison,
            "threshold_value": condition.value,
            "current_value": triggered_by.get("current_value"),
            "project_id": alert.project_id
        }
        
        # Store alert trigger in ChromaDB
        await self._add_to_chroma(
            self.collection_name,
            str(uuid.uuid4()),  # Generate unique ID for trigger
            notification,
            {
                "alert_id": str(alert.id),
                "task_id": str(task.id),
                "triggered_at": notification["triggered_at"],
                "notification_group": alert.notification_group
            }
        )
        
        return notification
    
    async def evaluate_conditions(
        self,
        task_id: UUID,
        metric_values: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Evaluate all conditions for a task and trigger alerts if needed"""
        
        stmt = select(Task).where(Task.id == task_id)
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        triggered_alerts = []
        
        for condition in task.conditions:
            metric_value = metric_values.get(condition.metric_name)
            
            if metric_value is not None:
                if await self._evaluate_condition(condition, metric_value):
                    # Trigger alert
                    if condition.alert:
                        notification = await self.trigger_alert(
                            condition.alert.id,
                            {"current_value": metric_value, "metric_values": metric_values}
                        )
                        triggered_alerts.append(notification)
                    
                    # Execute update action if defined
                    if condition.update:
                        await self._execute_update_action(condition.update, metric_value)
        
        return triggered_alerts
    
    async def _create_dataset(self, task_id: UUID, dataset_data: DatasetDetails) -> Dataset:
        """Create a dataset entity"""
        return Dataset(
            task_id=task_id,
            project_id=dataset_data.project_id or "",
            name=dataset_data.name,
            begin_date=datetime.strptime(dataset_data.begin_date, "%Y-%m-%d").date() if dataset_data.begin_date else None,
            end_date=datetime.strptime(dataset_data.end_date, "%Y-%m-%d").date() if dataset_data.end_date else None,
            time_dimension=dataset_data.time_dimension,
            indexes=dataset_data.indexes,
            columns=dataset_data.columns
        )
    
    async def _create_metric(self, task_id: UUID, metric_data: MetricDetails) -> Metric:
        """Create a metric entity"""
        return Metric(
            task_id=task_id,
            name=metric_data.metric_name,
            label=metric_data.label,
            description=metric_data.description,
            type=MetricType[metric_data.metric_type],
            type_params=metric_data.metric_params
        )
    
    async def _create_condition(
        self, 
        task_id: UUID, 
        condition_data: ConditionDetails,
        project_id: Optional[UUID] = None
    ) -> Condition:
        """Create a condition with optional alert and update action"""
        
        condition = Condition(
            task_id=task_id,
            name=condition_data.condition_name,
            condition_type=condition_data.condition_type,
            metric_name=condition_data.metric_name,
            comparison=condition_data.comparison,
            value=condition_data.value
        )
        
        self.db.add(condition)
        await self.db.flush()
        
        # Create alert if specified
        if condition_data.alert_details:
            alert = Alert(
                condition_id=condition.id,
                notification_group=condition_data.alert_details.get("notification_group", "default"),
                project_id=str(project_id) if project_id else ""
            )
            self.db.add(alert)
        
        # Create update action if specified
        if condition_data.update_details:
            update_action = UpdateAction(
                condition_id=condition.id,
                action=condition_data.update_details.get("action", "update state")
            )
            self.db.add(update_action)
        
        return condition
    
    async def _update_dataset(self, dataset: Dataset, update_data: DatasetDetails):
        """Update dataset entity"""
        if update_data.name:
            dataset.name = update_data.name
        if update_data.project_id:
            dataset.project_id = update_data.project_id
        if update_data.begin_date:
            dataset.begin_date = datetime.strptime(update_data.begin_date, "%Y-%m-%d").date()
        if update_data.end_date:
            dataset.end_date = datetime.strptime(update_data.end_date, "%Y-%m-%d").date()
        if update_data.time_dimension:
            dataset.time_dimension = update_data.time_dimension
        if update_data.indexes:
            dataset.indexes = update_data.indexes
        if update_data.columns:
            dataset.columns = update_data.columns
    
    async def _update_metric(self, metric: Metric, update_data: MetricDetails):
        """Update metric entity"""
        if update_data.metric_name:
            metric.name = update_data.metric_name
        if update_data.label:
            metric.label = update_data.label
        if update_data.description:
            metric.description = update_data.description
        if update_data.metric_type:
            metric.type = MetricType[update_data.metric_type]
        if update_data.metric_params:
            metric.type_params = update_data.metric_params
        metric.updated_at = datetime.utcnow()
    
    async def _update_condition(self, condition: Condition, update_data: ConditionDetails):
        """Update condition entity"""
        if update_data.condition_name:
            condition.name = update_data.condition_name
        if update_data.condition_type:
            condition.condition_type = update_data.condition_type
        if update_data.metric_name:
            condition.metric_name = update_data.metric_name
        if update_data.comparison:
            condition.comparison = update_data.comparison
        if update_data.value:
            condition.value = update_data.value
        
        # Update alert if exists
        if condition.alert and update_data.alert_details:
            if "notification_group" in update_data.alert_details:
                condition.alert.notification_group = update_data.alert_details["notification_group"]
        
        # Update action if exists
        if condition.update and update_data.update_details:
            if "action" in update_data.update_details:
                condition.update.action = update_data.update_details["action"]
        
        condition.updated_at = datetime.utcnow()
    
    async def _evaluate_condition(self, condition: Condition, value: Any) -> bool:
        """Evaluate if a condition is met"""
        
        threshold = condition.value.get("value")
        comparison = condition.comparison
        
        if comparison == "greaterthan":
            return value > threshold
        elif comparison == "lessthan":
            return value < threshold
        elif comparison == "equals":
            return value == threshold
        elif comparison == "notequals":
            return value != threshold
        elif comparison == "lessthanequal":
            return value <= threshold
        elif comparison == "isnull":
            return value is None
        elif comparison == "isnotnull":
            return value is not None
        # Add more comparison logic as needed
        
        return False
    
    async def _execute_update_action(self, update_action: UpdateAction, value: Any):
        """Execute an update action"""
        # Implement the action execution logic
        # This could update database records, trigger workflows, etc.
        pass
    
    async def _has_task_access(
        self,
        user_id: UUID,
        metadata: Dict[str, Any]
    ) -> bool:
        """Check if user has access to task"""
        
        # Owner always has access
        if metadata.get("created_by") == str(user_id):
            return True
        
        # Check workspace/project membership
        if metadata.get("workspace_id"):
            from app.models.workspace import WorkspaceAccess
            stmt = select(WorkspaceAccess).where(
                and_(
                    WorkspaceAccess.workspace_id == UUID(metadata["workspace_id"]),
                    WorkspaceAccess.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            access = result.scalar_one_or_none()
            if access:
                return True
        
        if metadata.get("project_id"):
            from app.models.workspace import ProjectAccess
            stmt = select(ProjectAccess).where(
                and_(
                    ProjectAccess.project_id == UUID(metadata["project_id"]),
                    ProjectAccess.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            access = result.scalar_one_or_none()
            if access:
                return True
        
        return False