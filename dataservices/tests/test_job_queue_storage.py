#!/usr/bin/env python3
"""
Test script for job queue service with configurable storage backends
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.job_queue_service import JobQueueService, JobType, JobStatus, JobData
from app.core.provider import CacheProvider, get_cache_provider

async def test_memory_storage():
    """Test job queue with in-memory storage"""
    print("🧠 Testing in-memory job queue storage...")
    
    # Create cache provider with memory cache
    cache_provider = CacheProvider(cache_type="memory")
    
    # Create job queue service
    job_queue = JobQueueService()
    
    # Register a simple test handler
    async def test_handler(job_data: JobData):
        print(f"Processing job {job_data.job_id} of type {job_data.job_type.value}")
        return {"status": "completed", "processed_at": datetime.utcnow().isoformat()}
    
    job_queue.register_handler(JobType.CHROMADB_INDEXING, test_handler)
    
    # Submit a test job
    job_id = await job_queue.submit_job(
        job_type=JobType.CHROMADB_INDEXING,
        project_id="test_project_001",
        user_id="test_user",
        priority=1
    )
    print(f"✅ Submitted job with ID: {job_id}")
    
    # Start worker
    await job_queue.start_worker()
    
    # Wait a bit for processing
    await asyncio.sleep(2)
    
    # Get job status
    job_status = await job_queue.get_job_status(job_id)
    if job_status:
        print(f"📊 Job status: {job_status.status.value}")
        if job_status.result:
            print(f"📋 Job result: {job_status.result}")
    
    # Get queue stats
    stats = await job_queue.get_queue_stats()
    print(f"📈 Queue stats: {stats}")
    
    # Stop worker
    await job_queue.stop_worker()
    await job_queue.disconnect()
    
    print("✅ In-memory storage test completed\n")

async def test_redis_storage():
    """Test job queue with Redis storage"""
    print("🔴 Testing Redis job queue storage...")
    
    try:
        # Create cache provider with Redis cache
        cache_provider = CacheProvider(cache_type="redis")
        
        # Create job queue service
        job_queue = JobQueueService()
        
        # Register a simple test handler
        async def test_handler(job_data: JobData):
            print(f"Processing job {job_data.job_id} of type {job_data.job_type.value}")
            return {"status": "completed", "processed_at": datetime.utcnow().isoformat()}
        
        job_queue.register_handler(JobType.CHROMADB_INDEXING, test_handler)
        
        # Submit a test job
        job_id = await job_queue.submit_job(
            job_type=JobType.CHROMADB_INDEXING,
            project_id="test_project_002",
            user_id="test_user",
            priority=1
        )
        print(f"✅ Submitted job with ID: {job_id}")
        
        # Start worker
        await job_queue.start_worker()
        
        # Wait a bit for processing
        await asyncio.sleep(2)
        
        # Get job status
        job_status = await job_queue.get_job_status(job_id)
        if job_status:
            print(f"📊 Job status: {job_status.status.value}")
            if job_status.result:
                print(f"📋 Job result: {job_status.result}")
        
        # Get queue stats
        stats = await job_queue.get_queue_stats()
        print(f"📈 Queue stats: {stats}")
        
        # Stop worker
        await job_queue.stop_worker()
        await job_queue.disconnect()
        
        print("✅ Redis storage test completed\n")
        
    except Exception as e:
        print(f"❌ Redis storage test failed: {e}")
        print("This is expected if Redis is not available\n")

async def test_cache_provider_info():
    """Test cache provider information"""
    print("🔧 Testing cache provider information...")
    
    # Test memory cache provider
    memory_provider = CacheProvider(cache_type="memory")
    memory_info = memory_provider.get_cache_info()
    print(f"📋 Memory cache info: {memory_info}")
    
    # Test Redis cache provider (if available)
    try:
        redis_provider = CacheProvider(cache_type="redis")
        redis_info = redis_provider.get_cache_info()
        print(f"📋 Redis cache info: {redis_info}")
    except Exception as e:
        print(f"❌ Redis cache provider failed: {e}")
    
    print("✅ Cache provider test completed\n")

async def main():
    """Main test function"""
    print("🚀 Starting job queue storage tests...\n")
    
    # Set required environment variables for testing
    os.environ.setdefault("OPENAI_API_KEY", "test_key")
    os.environ.setdefault("CHROMA_STORE_PATH", "./test_chroma_db")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/testdb")
    
    # Test cache provider information
    await test_cache_provider_info()
    
    # Test in-memory storage
    await test_memory_storage()
    
    # Test Redis storage (if available)
    await test_redis_storage()
    
    print("🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 