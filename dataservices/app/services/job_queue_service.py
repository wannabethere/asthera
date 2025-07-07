"""
Async Job Queue Service for Project JSON Schemas Processing
Handles background processing of project updates using configurable storage backend
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

from app.config.settings import get_settings
from app.core.provider import get_cache_provider

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


class JobType(Enum):
    """Job type enumeration"""
    PROJECT_JSON_TABLES = "project_json_tables"
    PROJECT_JSON_METRICS = "project_json_metrics"
    PROJECT_JSON_VIEWS = "project_json_views"
    PROJECT_JSON_CALCULATED_COLUMNS = "project_json_calculated_columns"
    PROJECT_JSON_SUMMARY = "project_json_summary"
    PROJECT_JSON_ALL = "project_json_all"
    CHROMADB_INDEXING = "chromadb_indexing"
    POST_COMMIT_WORKFLOW = "post_commit_workflow"


@dataclass
class JobData:
    """Job data structure"""
    job_id: str
    job_type: JobType
    project_id: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['job_type'] = self.job_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobData':
        """Create from dictionary from storage"""
        data['job_type'] = JobType(data['job_type'])
        data['status'] = JobStatus(data['status'])
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('started_at'):
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if data.get('completed_at'):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)


class JobQueueStorage(ABC):
    """Abstract base class for job queue storage backends"""
    
    @abstractmethod
    async def connect(self):
        """Connect to storage backend"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from storage backend"""
        pass
    
    @abstractmethod
    async def store_job(self, job_data: JobData) -> None:
        """Store job data"""
        pass
    
    @abstractmethod
    async def get_job(self) -> Optional[JobData]:
        """Get next job from queue"""
        pass
    
    @abstractmethod
    async def update_job(self, job_data: JobData) -> None:
        """Update job data"""
        pass
    
    @abstractmethod
    async def get_job_by_id(self, job_id: str) -> Optional[JobData]:
        """Get job by ID"""
        pass
    
    @abstractmethod
    async def remove_job_from_queue(self, job_id: str) -> bool:
        """Remove job from queue"""
        pass
    
    @abstractmethod
    async def add_job_to_queue(self, job_id: str, priority: int) -> None:
        """Add job to queue"""
        pass
    
    @abstractmethod
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        pass
    
    @abstractmethod
    async def cleanup_old_jobs(self, days: int) -> int:
        """Clean up old jobs"""
        pass


class InMemoryJobQueueStorage(JobQueueStorage):
    """In-memory job queue storage implementation"""
    
    def __init__(self):
        self.job_queue: List[tuple[int, str]] = []  # (priority, job_id)
        self.job_data: Dict[str, JobData] = {}
        self.is_connected = False
    
    async def connect(self):
        """Connect to in-memory storage"""
        self.is_connected = True
        logger.info("Connected to in-memory job queue storage")
    
    async def disconnect(self):
        """Disconnect from in-memory storage"""
        self.is_connected = False
        logger.info("Disconnected from in-memory job queue storage")
    
    async def store_job(self, job_data: JobData) -> None:
        """Store job data"""
        self.job_data[job_data.job_id] = job_data
    
    async def get_job(self) -> Optional[JobData]:
        """Get next job from queue"""
        if not self.job_queue:
            return None
        
        # Get job with highest priority (lowest score)
        self.job_queue.sort(key=lambda x: x[0])  # Sort by priority
        priority, job_id = self.job_queue.pop(0)
        
        return self.job_data.get(job_id)
    
    async def update_job(self, job_data: JobData) -> None:
        """Update job data"""
        self.job_data[job_data.job_id] = job_data
    
    async def get_job_by_id(self, job_id: str) -> Optional[JobData]:
        """Get job by ID"""
        return self.job_data.get(job_id)
    
    async def remove_job_from_queue(self, job_id: str) -> bool:
        """Remove job from queue"""
        for i, (priority, q_job_id) in enumerate(self.job_queue):
            if q_job_id == job_id:
                self.job_queue.pop(i)
                return True
        return False
    
    async def add_job_to_queue(self, job_id: str, priority: int) -> None:
        """Add job to queue"""
        self.job_queue.append((priority, job_id))
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        queue_length = len(self.job_queue)
        
        status_counts = {}
        for status in JobStatus:
            count = sum(1 for job in self.job_data.values() if job.status == status)
            status_counts[status.value] = count
        
        return {
            "queue_length": queue_length,
            "status_counts": status_counts
        }
    
    async def cleanup_old_jobs(self, days: int) -> int:
        """Clean up old jobs"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cleaned_count = 0
        
        job_ids_to_remove = []
        for job_id, job_data in self.job_data.items():
            if job_data.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                if job_data.completed_at and job_data.completed_at < cutoff_date:
                    job_ids_to_remove.append(job_id)
        
        for job_id in job_ids_to_remove:
            del self.job_data[job_id]
            await self.remove_job_from_queue(job_id)
            cleaned_count += 1
        
        return cleaned_count


class RedisJobQueueStorage(JobQueueStorage):
    """Redis job queue storage implementation"""
    
    def __init__(self, redis_config: Dict[str, Any]):
        self.redis_config = redis_config
        self.redis_client = None
        
        # Redis key prefixes
        self.JOB_QUEUE_KEY = "job_queue"
        self.JOB_DATA_KEY = "job_data"
    
    async def connect(self):
        """Connect to Redis"""
        try:
            import redis.asyncio as redis
            self.redis_client = redis.Redis(
                host=self.redis_config.get('host', 'localhost'),
                port=self.redis_config.get('port', 6379),
                db=self.redis_config.get('db', 0),
                password=self.redis_config.get('password'),
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Connected to Redis for job queue")
        except ImportError:
            raise ImportError("redis-py is not installed. Please install it to use Redis storage.")
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Disconnected from Redis")
    
    async def store_job(self, job_data: JobData) -> None:
        """Store job data"""
        await self.redis_client.hset(
            f"{self.JOB_DATA_KEY}:{job_data.job_id}",
            mapping=job_data.to_dict()
        )
    
    async def get_job(self) -> Optional[JobData]:
        """Get next job from queue"""
        # Get job with highest priority (lowest score)
        job_ids = await self.redis_client.zrange(self.JOB_QUEUE_KEY, 0, 0)
        if not job_ids:
            return None
        
        job_id = job_ids[0]
        
        # Get job data
        job_data_dict = await self.redis_client.hgetall(f"{self.JOB_DATA_KEY}:{job_id}")
        if not job_data_dict:
            # Remove invalid job from queue
            await self.redis_client.zrem(self.JOB_QUEUE_KEY, job_id)
            return None
        
        job_data = JobData.from_dict(job_data_dict)
        
        # Remove from queue
        await self.redis_client.zrem(self.JOB_QUEUE_KEY, job_id)
        
        return job_data
    
    async def update_job(self, job_data: JobData) -> None:
        """Update job data"""
        await self.redis_client.hset(
            f"{self.JOB_DATA_KEY}:{job_data.job_id}",
            mapping=job_data.to_dict()
        )
    
    async def get_job_by_id(self, job_id: str) -> Optional[JobData]:
        """Get job by ID"""
        job_data_dict = await self.redis_client.hgetall(f"{self.JOB_DATA_KEY}:{job_id}")
        if not job_data_dict:
            return None
        return JobData.from_dict(job_data_dict)
    
    async def remove_job_from_queue(self, job_id: str) -> bool:
        """Remove job from queue"""
        removed = await self.redis_client.zrem(self.JOB_QUEUE_KEY, job_id)
        return bool(removed)
    
    async def add_job_to_queue(self, job_id: str, priority: int) -> None:
        """Add job to queue"""
        await self.redis_client.zadd(self.JOB_QUEUE_KEY, {job_id: priority})
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        # Get queue length
        queue_length = await self.redis_client.zcard(self.JOB_QUEUE_KEY)
        
        # Get job counts by status
        status_counts = {}
        for status in JobStatus:
            pattern = f"{self.JOB_DATA_KEY}:*"
            count = 0
            async for key in self.redis_client.scan_iter(match=pattern):
                job_data_dict = await self.redis_client.hgetall(key)
                if job_data_dict.get('status') == status.value:
                    count += 1
            status_counts[status.value] = count
        
        return {
            "queue_length": queue_length,
            "status_counts": status_counts
        }
    
    async def cleanup_old_jobs(self, days: int) -> int:
        """Clean up old completed/failed jobs"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        pattern = f"{self.JOB_DATA_KEY}:*"
        
        cleaned_count = 0
        async for key in self.redis_client.scan_iter(match=pattern):
            job_data_dict = await self.redis_client.hgetall(key)
            if job_data_dict.get('status') in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
                completed_at = job_data_dict.get('completed_at')
                if completed_at:
                    job_date = datetime.fromisoformat(completed_at)
                    if job_date < cutoff_date:
                        await self.redis_client.delete(key)
                        cleaned_count += 1
        
        return cleaned_count


class JobQueueService:
    """Async job queue service with configurable storage backend"""
    
    def __init__(self):
        self.settings = get_settings()
        self.storage: Optional[JobQueueStorage] = None
        self.job_handlers: Dict[JobType, Callable] = {}
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        self._initialize_storage()
    
    def _initialize_storage(self):
        """Initialize storage backend based on cache provider configuration"""
        try:
            cache_provider = get_cache_provider()
            cache_info = cache_provider.get_cache_info()
            
            # Check if Redis cache is available
            if any(info.get('type') == 'RedisCacheProvider' for info in cache_info.values()):
                # Use Redis storage
                redis_config = {
                    'host': getattr(self.settings, 'REDIS_HOST', 'localhost'),
                    'port': getattr(self.settings, 'REDIS_PORT', 6379),
                    'db': getattr(self.settings, 'REDIS_DB', 0),
                    'password': getattr(self.settings, 'REDIS_PASSWORD', None)
                }
                self.storage = RedisJobQueueStorage(redis_config)
                logger.info("Initialized Redis job queue storage")
            else:
                # Use in-memory storage
                self.storage = InMemoryJobQueueStorage()
                logger.info("Initialized in-memory job queue storage")
                
        except Exception as e:
            logger.warning(f"Failed to initialize Redis storage, falling back to in-memory: {e}")
            self.storage = InMemoryJobQueueStorage()
            logger.info("Initialized in-memory job queue storage as fallback")
    
    async def connect(self):
        """Connect to storage backend"""
        if self.storage:
            await self.storage.connect()
    
    async def disconnect(self):
        """Disconnect from storage backend"""
        if self.storage:
            await self.storage.disconnect()
    
    async def submit_job(
        self,
        job_type: JobType,
        project_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit a new job to the queue"""
        await self.connect()
        
        job_id = str(uuid.uuid4())
        job_data = JobData(
            job_id=job_id,
            job_type=job_type,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            session_id=session_id,
            priority=priority,
            created_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        # Store job data
        await self.storage.store_job(job_data)
        
        # Add to queue
        await self.storage.add_job_to_queue(job_id, priority)
        
        logger.info(f"Submitted job {job_id} of type {job_type.value} for project {project_id}")
        return job_id
    
    async def get_job(self) -> Optional[JobData]:
        """Get the next job from the queue"""
        await self.connect()
        return await self.storage.get_job()
    
    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Update job status and result"""
        await self.connect()
        
        job_data = await self.storage.get_job_by_id(job_id)
        if not job_data:
            logger.warning(f"Job {job_id} not found for status update")
            return
        
        job_data.status = status
        
        if status == JobStatus.RUNNING:
            job_data.started_at = datetime.utcnow()
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            job_data.completed_at = datetime.utcnow()
            job_data.result = result
            job_data.error = error
        
        # Update job data
        await self.storage.update_job(job_data)
        
        logger.info(f"Updated job {job_id} status to {status.value}")
    
    async def get_job_status(self, job_id: str) -> Optional[JobData]:
        """Get job status and data"""
        await self.connect()
        return await self.storage.get_job_by_id(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job"""
        await self.connect()
        
        # Remove from queue
        removed = await self.storage.remove_job_from_queue(job_id)
        if removed:
            await self.update_job_status(job_id, JobStatus.CANCELLED)
            logger.info(f"Cancelled job {job_id}")
            return True
        
        return False
    
    async def retry_job(self, job_id: str) -> bool:
        """Retry a failed job"""
        await self.connect()
        
        job_data = await self.storage.get_job_by_id(job_id)
        if not job_data or job_data.status != JobStatus.FAILED:
            return False
        
        if job_data.retry_count >= job_data.max_retries:
            logger.warning(f"Job {job_id} has exceeded max retries")
            return False
        
        # Reset job for retry
        job_data.retry_count += 1
        job_data.status = JobStatus.PENDING
        job_data.started_at = None
        job_data.completed_at = None
        job_data.result = None
        job_data.error = None
        
        # Update job data
        await self.storage.update_job(job_data)
        
        # Add back to queue with higher priority
        await self.storage.add_job_to_queue(job_id, job_data.priority - 1)
        
        logger.info(f"Retried job {job_id} (attempt {job_data.retry_count})")
        return True
    
    def register_handler(self, job_type: JobType, handler: Callable):
        """Register a job handler function"""
        self.job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type {job_type.value}")
    
    async def process_job(self, job_data: JobData):
        """Process a single job"""
        try:
            await self.update_job_status(job_data.job_id, JobStatus.RUNNING)
            
            handler = self.job_handlers.get(job_data.job_type)
            if not handler:
                raise Exception(f"No handler registered for job type {job_data.job_type.value}")
            
            # Execute job handler
            result = await handler(job_data)
            
            await self.update_job_status(job_data.job_id, JobStatus.COMPLETED, result=result)
            logger.info(f"Completed job {job_data.job_id}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed job {job_data.job_id}: {error_msg}")
            
            # Check if job should be retried
            if job_data.retry_count < job_data.max_retries:
                await self.update_job_status(job_data.job_id, JobStatus.RETRY, error=error_msg)
                await self.retry_job(job_data.job_id)
            else:
                await self.update_job_status(job_data.job_id, JobStatus.FAILED, error=error_msg)
    
    async def worker_loop(self):
        """Main worker loop for processing jobs"""
        logger.info("Starting job queue worker")
        
        while self.is_running:
            try:
                job_data = await self.get_job()
                if job_data:
                    await self.process_job(job_data)
                else:
                    # No jobs available, wait a bit
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def start_worker(self):
        """Start the job queue worker"""
        if self.is_running:
            logger.warning("Worker is already running")
            return
        
        self.is_running = True
        self.worker_task = asyncio.create_task(self.worker_loop())
        logger.info("Job queue worker started")
    
    async def stop_worker(self):
        """Stop the job queue worker"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Job queue worker stopped")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        await self.connect()
        
        stats = await self.storage.get_queue_stats()
        stats["worker_running"] = self.is_running
        return stats
    
    async def cleanup_old_jobs(self, days: int = 7):
        """Clean up old completed/failed jobs"""
        await self.connect()
        
        cleaned_count = await self.storage.cleanup_old_jobs(days)
        logger.info(f"Cleaned up {cleaned_count} old jobs")


# Global job queue service instance
job_queue_service = JobQueueService() 