#!/usr/bin/env python3
"""
Test script for async job queue functionality
"""

import asyncio
import json
from datetime import datetime
from app.services.job_queue_service import job_queue_service, JobType, JobStatus, JobData
from app.services.entity_update_service import entity_update_service
from app.services.job_handlers import job_handlers
from app.core.session_manager import SessionManager
from app.core.settings import ServiceConfig

async def test_job_queue_basic_operations():
    """Test basic job queue operations"""
    
    print("🚀 Starting async job queue basic operations test...")
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    
    try:
        # Test 1: Submit a job
        print("\n📋 Test 1: Submitting a job...")
        job_id = await job_queue_service.submit_job(
            job_type=JobType.PROJECT_JSON_TABLES,
            project_id="test_project_001",
            entity_type="table",
            entity_id="test_table_001",
            user_id="test_user",
            session_id="test_session",
            priority=1,
            metadata={"test": True}
        )
        
        print(f"✅ Job submitted with ID: {job_id}")
        
        # Test 2: Get job status
        print("\n📊 Test 2: Getting job status...")
        job_data = await job_queue_service.get_job_status(job_id)
        if job_data:
            print(f"✅ Job status: {job_data.status.value}")
            print(f"   Project ID: {job_data.project_id}")
            print(f"   Job type: {job_data.job_type.value}")
            print(f"   Created at: {job_data.created_at}")
        else:
            print("❌ Job not found")
        
        # Test 3: Get queue stats
        print("\n📈 Test 3: Getting queue stats...")
        stats = await job_queue_service.get_queue_stats()
        print(f"✅ Queue length: {stats['queue_length']}")
        print(f"   Status counts: {stats['status_counts']}")
        print(f"   Worker running: {stats['worker_running']}")
        
        # Test 4: Cancel job
        print("\n❌ Test 4: Cancelling job...")
        success = await job_queue_service.cancel_job(job_id)
        if success:
            print("✅ Job cancelled successfully")
        else:
            print("❌ Failed to cancel job")
        
        print("\n✅ Basic job queue operations test completed!")
        
    except Exception as e:
        print(f"❌ Error during basic job queue test: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_entity_update_service():
    """Test entity update service functionality"""
    
    print("\n🧪 Testing entity update service...")
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    
    try:
        project_id = "entity_test_project_001"
        user_id = "test_user"
        session_id = "test_session"
        
        # Test 1: Table update
        print("\n📋 Test 1: Table update...")
        table_result = await entity_update_service.on_table_updated(
            project_id=project_id,
            table_id="test_table_001",
            user_id=user_id,
            session_id=session_id,
            metadata={"test_type": "table_update"}
        )
        print(f"✅ Table update jobs submitted: {table_result}")
        
        # Test 2: Column update
        print("\n📝 Test 2: Column update...")
        column_result = await entity_update_service.on_column_updated(
            project_id=project_id,
            table_id="test_table_001",
            column_id="test_column_001",
            user_id=user_id,
            session_id=session_id,
            metadata={"test_type": "column_update"}
        )
        print(f"✅ Column update jobs submitted: {column_result}")
        
        # Test 3: Metric update
        print("\n📊 Test 3: Metric update...")
        metric_result = await entity_update_service.on_metric_updated(
            project_id=project_id,
            metric_id="test_metric_001",
            user_id=user_id,
            session_id=session_id,
            metadata={"test_type": "metric_update"}
        )
        print(f"✅ Metric update jobs submitted: {metric_result}")
        
        # Test 4: View update
        print("\n👁️ Test 4: View update...")
        view_result = await entity_update_service.on_view_updated(
            project_id=project_id,
            view_id="test_view_001",
            user_id=user_id,
            session_id=session_id,
            metadata={"test_type": "view_update"}
        )
        print(f"✅ View update jobs submitted: {view_result}")
        
        # Test 5: Calculated column update
        print("\n🧮 Test 5: Calculated column update...")
        calc_column_result = await entity_update_service.on_calculated_column_updated(
            project_id=project_id,
            calculated_column_id="test_calc_column_001",
            user_id=user_id,
            session_id=session_id,
            metadata={"test_type": "calculated_column_update"}
        )
        print(f"✅ Calculated column update jobs submitted: {calc_column_result}")
        
        # Test 6: Project commit
        print("\n🚀 Test 6: Project commit...")
        commit_result = await entity_update_service.on_project_committed(
            project_id=project_id,
            user_id=user_id,
            session_id=session_id,
            metadata={"test_type": "project_commit"}
        )
        print(f"✅ Project commit job submitted: {commit_result}")
        
        # Test 7: Get queue stats after all updates
        print("\n📈 Test 7: Queue stats after updates...")
        stats = await job_queue_service.get_queue_stats()
        print(f"✅ Queue length: {stats['queue_length']}")
        print(f"   Status counts: {stats['status_counts']}")
        
        print("\n✅ Entity update service test completed!")
        
    except Exception as e:
        print(f"❌ Error during entity update service test: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_job_handlers():
    """Test job handlers functionality"""
    
    print("\n🔧 Testing job handlers...")
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    
    try:
        # Create test job data
        job_data = JobData(
            job_id="test_handler_job_001",
            job_type=JobType.PROJECT_JSON_TABLES,
            project_id="handler_test_project_001",
            entity_type="table",
            entity_id="test_table_001",
            user_id="test_user",
            session_id="test_session",
            created_at=datetime.utcnow()
        )
        
        # Test 1: Tables handler
        print("\n📋 Test 1: Testing tables handler...")
        try:
            result = await job_handlers.handle_project_json_tables(job_data)
            print(f"✅ Tables handler result: {result}")
        except Exception as e:
            print(f"⚠️ Tables handler error (expected if no real project): {str(e)}")
        
        # Test 2: Metrics handler
        print("\n📊 Test 2: Testing metrics handler...")
        job_data.job_type = JobType.PROJECT_JSON_METRICS
        job_data.entity_type = "metric"
        job_data.entity_id = "test_metric_001"
        
        try:
            result = await job_handlers.handle_project_json_metrics(job_data)
            print(f"✅ Metrics handler result: {result}")
        except Exception as e:
            print(f"⚠️ Metrics handler error (expected if no real project): {str(e)}")
        
        # Test 3: Views handler
        print("\n👁️ Test 3: Testing views handler...")
        job_data.job_type = JobType.PROJECT_JSON_VIEWS
        job_data.entity_type = "view"
        job_data.entity_id = "test_view_001"
        
        try:
            result = await job_handlers.handle_project_json_views(job_data)
            print(f"✅ Views handler result: {result}")
        except Exception as e:
            print(f"⚠️ Views handler error (expected if no real project): {str(e)}")
        
        # Test 4: Calculated columns handler
        print("\n🧮 Test 4: Testing calculated columns handler...")
        job_data.job_type = JobType.PROJECT_JSON_CALCULATED_COLUMNS
        job_data.entity_type = "calculated_column"
        job_data.entity_id = "test_calc_column_001"
        
        try:
            result = await job_handlers.handle_project_json_calculated_columns(job_data)
            print(f"✅ Calculated columns handler result: {result}")
        except Exception as e:
            print(f"⚠️ Calculated columns handler error (expected if no real project): {str(e)}")
        
        # Test 5: Summary handler
        print("\n📋 Test 5: Testing summary handler...")
        job_data.job_type = JobType.PROJECT_JSON_SUMMARY
        job_data.entity_type = "project"
        job_data.entity_id = "handler_test_project_001"
        
        try:
            result = await job_handlers.handle_project_json_summary(job_data)
            print(f"✅ Summary handler result: {result}")
        except Exception as e:
            print(f"⚠️ Summary handler error (expected if no real project): {str(e)}")
        
        print("\n✅ Job handlers test completed!")
        
    except Exception as e:
        print(f"❌ Error during job handlers test: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_worker_functionality():
    """Test worker functionality"""
    
    print("\n⚙️ Testing worker functionality...")
    
    try:
        # Test 1: Start worker
        print("\n🚀 Test 1: Starting worker...")
        await job_queue_service.start_worker()
        print("✅ Worker started")
        
        # Wait a bit for worker to initialize
        await asyncio.sleep(2)
        
        # Test 2: Submit a test job
        print("\n📋 Test 2: Submitting test job...")
        job_id = await job_queue_service.submit_job(
            job_type=JobType.PROJECT_JSON_TABLES,
            project_id="worker_test_project_001",
            entity_type="table",
            entity_id="test_table_001",
            user_id="test_user",
            session_id="test_session",
            priority=0
        )
        print(f"✅ Test job submitted: {job_id}")
        
        # Wait for job to be processed
        print("\n⏳ Waiting for job processing...")
        await asyncio.sleep(5)
        
        # Test 3: Check job status
        print("\n📊 Test 3: Checking job status...")
        job_data = await job_queue_service.get_job_status(job_id)
        if job_data:
            print(f"✅ Job status: {job_data.status.value}")
            if job_data.result:
                print(f"   Result: {job_data.result}")
            if job_data.error:
                print(f"   Error: {job_data.error}")
        else:
            print("❌ Job not found")
        
        # Test 4: Stop worker
        print("\n🛑 Test 4: Stopping worker...")
        await job_queue_service.stop_worker()
        print("✅ Worker stopped")
        
        print("\n✅ Worker functionality test completed!")
        
    except Exception as e:
        print(f"❌ Error during worker test: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_bulk_operations():
    """Test bulk operations"""
    
    print("\n📦 Testing bulk operations...")
    
    try:
        project_id = "bulk_test_project_001"
        user_id = "test_user"
        session_id = "test_session"
        
        # Create bulk update data
        entity_updates = [
            {
                "entity_type": "table",
                "entity_id": "bulk_table_001"
            },
            {
                "entity_type": "metric",
                "entity_id": "bulk_metric_001"
            },
            {
                "entity_type": "view",
                "entity_id": "bulk_view_001"
            },
            {
                "entity_type": "calculated_column",
                "entity_id": "bulk_calc_column_001"
            }
        ]
        
        # Test bulk update
        print("\n📋 Test 1: Bulk entity update...")
        result = await entity_update_service.on_bulk_update(
            project_id=project_id,
            entity_updates=entity_updates,
            user_id=user_id,
            session_id=session_id,
            metadata={"test_type": "bulk_update"}
        )
        print(f"✅ Bulk update result: {result}")
        
        # Check queue stats
        print("\n📈 Test 2: Queue stats after bulk update...")
        stats = await job_queue_service.get_queue_stats()
        print(f"✅ Queue length: {stats['queue_length']}")
        print(f"   Status counts: {stats['status_counts']}")
        
        print("\n✅ Bulk operations test completed!")
        
    except Exception as e:
        print(f"❌ Error during bulk operations test: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_error_handling():
    """Test error handling and retry functionality"""
    
    print("\n⚠️ Testing error handling...")
    
    try:
        # Test 1: Submit a job with invalid project
        print("\n📋 Test 1: Submitting job with invalid project...")
        job_id = await job_queue_service.submit_job(
            job_type=JobType.PROJECT_JSON_TABLES,
            project_id="invalid_project_999",
            entity_type="table",
            entity_id="invalid_table_999",
            user_id="test_user",
            session_id="test_session",
            priority=0
        )
        print(f"✅ Job submitted: {job_id}")
        
        # Start worker to process the job
        await job_queue_service.start_worker()
        await asyncio.sleep(5)
        
        # Check job status (should be failed)
        job_data = await job_queue_service.get_job_status(job_id)
        if job_data:
            print(f"✅ Job status: {job_data.status.value}")
            if job_data.error:
                print(f"   Error: {job_data.error}")
            
            # Test 2: Retry failed job
            if job_data.status == JobStatus.FAILED:
                print("\n🔄 Test 2: Retrying failed job...")
                success = await job_queue_service.retry_job(job_id)
                if success:
                    print("✅ Job retried successfully")
                else:
                    print("❌ Failed to retry job")
        
        # Stop worker
        await job_queue_service.stop_worker()
        
        print("\n✅ Error handling test completed!")
        
    except Exception as e:
        print(f"❌ Error during error handling test: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_chromadb_indexing():
    """Test ChromaDB indexing functionality"""
    
    print("\n🔍 Testing ChromaDB indexing...")
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    
    try:
        # Create a test project with MDL file
        async with session_manager.get_async_db_session() as db:
            from app.schemas.dbmodels import Project, Dataset, Table, SQLColumn
            import json
            import os
            from pathlib import Path
            
            # Create test project
            project = Project(
                project_id="chromadb_test_project_001",
                display_name="ChromaDB Indexing Test Project",
                description="Test project for ChromaDB indexing",
                created_by="test_user",
                status='committed',
                version_locked=True,
                json_metadata={
                    "llm_definitions": {
                        "generated_at": datetime.utcnow().isoformat(),
                        "mdl_file_path": "mdl_files/chromadb_test_project_001/test_mdl.json",
                        "definitions_count": 1,
                        "tables_processed": 1
                    }
                }
            )
            
            db.add(project)
            await db.commit()
            await db.refresh(project)
            
            # Create test MDL file
            mdl_dir = Path("mdl_files/chromadb_test_project_001")
            mdl_dir.mkdir(parents=True, exist_ok=True)
            
            test_mdl = {
                "project_id": "chromadb_test_project_001",
                "project_name": "ChromaDB Indexing Test Project",
                "description": "Test project for ChromaDB indexing",
                "generated_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                "tables": [
                    {
                        "table_id": "test_table_001",
                        "table_name": "customers",
                        "display_name": "Customers",
                        "description": "Customer master data table with comprehensive business context",
                        "business_purpose": "Store and manage customer information for sales and marketing activities",
                        "primary_use_cases": ["Customer analytics", "Sales reporting", "Marketing campaigns"],
                        "key_relationships": ["Orders", "Payments", "Customer segments"],
                        "data_lineage": "Extracted from CRM system and enriched with external data",
                        "update_frequency": "Daily",
                        "data_retention": "7 years",
                        "access_patterns": ["Read-heavy", "Batch updates", "Real-time queries"],
                        "performance_considerations": ["Indexed on customer_id", "Partitioned by region"],
                        "columns": [
                            {
                                "name": "customer_id",
                                "display_name": "Customer ID",
                                "description": "Unique customer identifier",
                                "business_description": "Primary key for customer records, used across all customer-related processes",
                                "usage_type": "identifier",
                                "data_type": "VARCHAR(50)",
                                "example_values": ["CUST001", "CUST002"],
                                "business_rules": ["Must be unique", "Cannot be null"],
                                "data_quality_checks": ["Uniqueness", "Format validation"],
                                "related_concepts": ["Customer", "Account", "Profile"],
                                "privacy_classification": "PII",
                                "aggregation_suggestions": ["Count", "Distinct count"],
                                "filtering_suggestions": ["Exact match", "Pattern matching"]
                            },
                            {
                                "name": "customer_name",
                                "display_name": "Customer Name",
                                "description": "Full name of the customer",
                                "business_description": "Customer's full legal name as provided during registration",
                                "usage_type": "attribute",
                                "data_type": "VARCHAR(100)",
                                "example_values": ["John Doe", "Jane Smith"],
                                "business_rules": ["Cannot be null", "Minimum 2 characters"],
                                "data_quality_checks": ["Length validation", "Character validation"],
                                "related_concepts": ["Name", "Person", "Contact"],
                                "privacy_classification": "PII",
                                "aggregation_suggestions": ["Count", "Group by"],
                                "filtering_suggestions": ["Partial match", "Case insensitive"]
                            }
                        ]
                    }
                ],
                "metadata": {
                    "total_tables": 1,
                    "business_domain": "E-commerce",
                    "target_users": ["Data Analysts", "Business Users"],
                    "key_concepts": ["Customer", "Order", "Product"]
                }
            }
            
            mdl_file_path = mdl_dir / "test_mdl.json"
            with open(mdl_file_path, 'w', encoding='utf-8') as f:
                json.dump(test_mdl, f, indent=2, ensure_ascii=False)
            
            # Update project metadata with correct file path
            project.json_metadata["llm_definitions"]["mdl_file_path"] = str(mdl_file_path)
            await db.commit()
            
            print("✅ Test project and MDL file created")
        
        # Test 1: Submit ChromaDB indexing job
        print("\n🔍 Test 1: Submitting ChromaDB indexing job...")
        job_id = await job_queue_service.submit_job(
            job_type=JobType.CHROMADB_INDEXING,
            project_id="chromadb_test_project_001",
            entity_type="project",
            entity_id="chromadb_test_project_001",
            user_id="test_user",
            session_id="test_session",
            priority=1,
            metadata={"test_type": "chromadb_indexing"}
        )
        print(f"✅ ChromaDB indexing job submitted: {job_id}")
        
        # Test 2: Start worker and process job
        print("\n⚙️ Test 2: Processing ChromaDB indexing job...")
        await job_queue_service.start_worker()
        await asyncio.sleep(10)  # Give more time for indexing
        
        # Test 3: Check job status
        print("\n📊 Test 3: Checking job status...")
        job_data = await job_queue_service.get_job_status(job_id)
        if job_data:
            print(f"✅ Job status: {job_data.status.value}")
            if job_data.result:
                print(f"   Indexing results: {job_data.result.get('indexing_results', {})}")
            if job_data.error:
                print(f"   Error: {job_data.error}")
        else:
            print("❌ Job not found")
        
        # Test 4: Check project metadata update
        print("\n📋 Test 4: Checking project metadata update...")
        async with session_manager.get_async_db_session() as db:
            result = await db.execute(
                select(Project).where(Project.project_id == "chromadb_test_project_001")
            )
            updated_project = result.scalar_one_or_none()
            
            if updated_project and updated_project.json_metadata:
                chromadb_indexing = updated_project.json_metadata.get("chromadb_indexing")
                if chromadb_indexing:
                    print(f"✅ ChromaDB indexing metadata found")
                    print(f"   Indexed at: {chromadb_indexing.get('indexed_at')}")
                    print(f"   Indexed by: {chromadb_indexing.get('indexed_by')}")
                    print(f"   Results: {chromadb_indexing.get('results', {})}")
                else:
                    print("❌ ChromaDB indexing metadata not found")
        
        # Stop worker
        await job_queue_service.stop_worker()
        
        # Cleanup test files
        if mdl_file_path.exists():
            mdl_file_path.unlink()
        if mdl_dir.exists():
            mdl_dir.rmdir()
        
        print("\n✅ ChromaDB indexing test completed!")
        
    except Exception as e:
        print(f"❌ Error during ChromaDB indexing test: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run all tests
    print("🧪 Starting async job queue tests...\n")
    
    # Test basic operations
    asyncio.run(test_job_queue_basic_operations())
    
    # Test entity update service
    asyncio.run(test_entity_update_service())
    
    # Test job handlers
    asyncio.run(test_job_handlers())
    
    # Test worker functionality
    asyncio.run(test_worker_functionality())
    
    # Test bulk operations
    asyncio.run(test_bulk_operations())
    
    # Test error handling
    asyncio.run(test_error_handling())
    
    # Test ChromaDB indexing
    asyncio.run(test_chromadb_indexing())
    
    print("\n🎉 All async job queue tests completed!") 