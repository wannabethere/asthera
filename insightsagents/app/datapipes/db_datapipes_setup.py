"""
Database Setup and Migration Scripts
===================================
"""

# scripts/init_db.py - Database initialization script
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database_models import create_database_engine, init_database, Base
from pipeline_database_service import PipelineDatabaseService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def initialize_database(database_url: str = None, create_sample_data: bool = False):
    """Initialize database with schema and optional sample data"""
    
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///pipeline_codes.db")
    
    logger.info(f"Initializing database: {database_url}")
    
    try:
        # Create engine and tables
        engine = create_database_engine(database_url)
        init_database(engine)
        
        logger.info("✅ Database schema created successfully")
        
        # Create sample data if requested
        if create_sample_data:
            await create_sample_data_async(database_url)
        
        logger.info("✅ Database initialization completed")
        
    except Exception as e:
        logger.error(f"❌ Error initializing database: {str(e)}")
        raise


async def create_sample_data_async(database_url: str):
    """Create sample pipeline data for testing"""
    
    logger.info("Creating sample data...")
    
    db_service = PipelineDatabaseService(database_url=database_url, enable_chroma=False)
    
    sample_pipelines = [
        {
            "question": "Find anomalies in daily spending patterns",
            "analysis_type": "anomaly_detection",
            "pipeline_type": "MetricsPipe",
            "function_name": "GroupBy",
            "code": '''
"""
Generated Pipeline Code
Analysis: anomaly_detection
Question: Find anomalies in daily spending patterns
Pipeline Type: MetricsPipe
Function: GroupBy
Status: success
Generated on: 2025-09-01 12:36:05
"""

import pandas as pd
import numpy as np
from app.tools.mltools import MetricsPipe, GroupBy, AnomalyPipe, detect_contextual_anomalies

def run_generated_pipeline(df):
    result = (
        MetricsPipe.from_dataframe("Purchase Orders Data")
        | GroupBy(by='Date, Region, Project', agg_dict={'Transactional value': 'sum'})
    ).to_df()
    
    result = (
        AnomalyPipe.from_dataframe(result)
        | detect_contextual_anomalies()
    ).to_df()
    
    return result
''',
            "user_id": "demo_user",
            "tags": ["sample", "anomaly_detection"]
        },
        {
            "question": "Analyze customer segmentation patterns by purchase behavior",
            "analysis_type": "segmentation",
            "pipeline_type": "SegmentationPipe", 
            "function_name": "run_kmeans",
            "code": '''
"""
Generated Pipeline Code
Analysis: segmentation
Question: Analyze customer segmentation patterns by purchase behavior
Pipeline Type: SegmentationPipe
Function: run_kmeans
Status: success
Generated on: 2025-09-01 12:40:15
"""

import pandas as pd
import numpy as np
from app.tools.mltools import SegmentationPipe, run_kmeans, generate_summary

def run_generated_pipeline(df):
    result = (
        SegmentationPipe.from_dataframe("Customer Data")
        | run_kmeans(n_clusters=5, features=['purchase_frequency', 'total_spent', 'avg_order_value'])
    ).to_df()
    
    summary = (
        SegmentationPipe.from_dataframe(result)
        | generate_summary()
    ).to_df()
    
    return result, summary
''',
            "user_id": "demo_user",
            "tags": ["sample", "segmentation", "customers"]
        },
        {
            "question": "Calculate growth trends in monthly revenue by region",
            "analysis_type": "trend_analysis",
            "pipeline_type": "TrendPipe",
            "function_name": "calculate_growth_rates",
            "code": '''
"""
Generated Pipeline Code
Analysis: trend_analysis
Question: Calculate growth trends in monthly revenue by region
Pipeline Type: TrendPipe
Function: calculate_growth_rates
Status: success
Generated on: 2025-09-01 12:45:30
"""

import pandas as pd
import numpy as np
from app.tools.mltools import TrendPipe, aggregate_by_time, calculate_growth_rates, forecast_metric

def run_generated_pipeline(df):
    # Aggregate by month and region
    monthly_data = (
        TrendPipe.from_dataframe("Revenue Data")
        | aggregate_by_time(time_column='date', group_by=['region'], aggregation='sum', period='M')
    ).to_df()
    
    # Calculate growth rates
    growth_rates = (
        TrendPipe.from_dataframe(monthly_data)
        | calculate_growth_rates(metric_column='revenue', group_by=['region'])
    ).to_df()
    
    # Generate forecast
    forecast = (
        TrendPipe.from_dataframe(monthly_data)
        | forecast_metric(metric_column='revenue', periods=6, group_by=['region'])
    ).to_df()
    
    return growth_rates, forecast
''',
            "user_id": "demo_user",
            "tags": ["sample", "trend_analysis", "revenue"]
        }
    ]
    
    try:
        for i, pipeline_data in enumerate(sample_pipelines):
            from pipeline_database_service import PipelineMetadata
            from datetime import datetime
            
            metadata = PipelineMetadata(
                question=pipeline_data["question"],
                analysis_type=pipeline_data["analysis_type"],
                pipeline_type=pipeline_data["pipeline_type"],
                function_name=pipeline_data["function_name"],
                status="success",
                generated_on=datetime.utcnow(),
                additional_metadata={
                    "sample_data": True,
                    "created_by": "init_script"
                }
            )
            
            pipeline = await db_service.save_pipeline_code(
                code=pipeline_data["code"],
                metadata=metadata,
                user_id=pipeline_data["user_id"],
                tags=pipeline_data["tags"]
            )
            
            logger.info(f"  ✅ Created sample pipeline {i+1}: {pipeline.id}")
        
        logger.info(f"✅ Created {len(sample_pipelines)} sample pipelines")
        
    except Exception as e:
        logger.error(f"❌ Error creating sample data: {str(e)}")
        raise


def create_migration():
    """Create a new Alembic migration"""
    import subprocess
    
    message = input("Enter migration message: ")
    if not message:
        message = "Auto migration"
    
    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Migration created successfully:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating migration: {e.stderr}")


def run_migrations():
    """Run pending Alembic migrations"""
    import subprocess
    
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Migrations completed successfully:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running migrations: {e.stderr}")


# scripts/init_db.sql - PostgreSQL initialization script
INIT_DB_SQL = """
-- Initial database setup for PostgreSQL
-- This file is automatically executed when the PostgreSQL container starts

-- Create additional schemas if needed
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Create indexes for performance (these will be created by SQLAlchemy, but kept for reference)
-- Additional indexes can be added here

-- Create initial admin user (optional)
-- INSERT INTO users (id, username, email, is_admin) VALUES 
-- ('admin-001', 'admin', 'admin@yourcompany.com', true);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE pipeline_codes TO pipeline_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pipeline_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pipeline_user;

-- Set default schema
ALTER USER pipeline_user SET search_path TO public;

-- Create extension for UUID generation if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Initial configuration
INSERT INTO pipeline_analytics (date, total_generations, successful_generations, failed_generations, 
                               total_executions, successful_executions, failed_executions)
VALUES (CURRENT_DATE, 0, 0, 0, 0, 0, 0)
ON CONFLICT (date) DO NOTHING;
"""


# scripts/setup.py - Main setup script
import asyncio
import sys
import os
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    parser = argparse.ArgumentParser(description="Setup Pipeline Database Service")
    parser.add_argument("--database-url", help="Database URL")
    parser.add_argument("--create-sample-data", action="store_true", help="Create sample data")
    parser.add_argument("--run-migrations", action="store_true", help="Run database migrations")
    parser.add_argument("--create-migration", action="store_true", help="Create new migration")
    parser.add_argument("--init-only", action="store_true", help="Initialize database schema only")
    
    args = parser.parse_args()
    
    database_url = args.database_url or os.getenv("DATABASE_URL", "sqlite:///pipeline_codes.db")
    
    print("🚀 Pipeline Database Service Setup")
    print(f"Database URL: {database_url}")
    print("=" * 50)
    
    try:
        if args.create_migration:
            print("📝 Creating new migration...")
            create_migration()
            return
        
        if args.run_migrations:
            print("⬆️ Running database migrations...")
            run_migrations()
            return
        
        # Initialize database
        if not args.init_only:
            print("🔧 Initializing database...")
            await initialize_database(database_url, args.create_sample_data)
        else:
            print("🔧 Initializing database schema only...")
            await initialize_database(database_url, False)
        
        print("\n✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the service: python enhanced_pipeline_api.py")
        print("2. Visit http://localhost:8000/docs for API documentation")
        print("3. Visit http://localhost:8000/health to check service health")
        
        if "postgresql" in database_url.lower():
            print("4. Visit http://localhost:8080 for database management (Adminer)")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {str(e)}")
        sys.exit(1)


# scripts/check_health.py - Health check script
async def check_service_health():
    """Check the health of all services"""
    import httpx
    
    services = [
        ("Pipeline API", "http://localhost:8000/health"),
        ("Database", None),  # Checked via API
        ("Redis", "redis://localhost:6379"),
    ]
    
    print("🔍 Checking service health...")
    print("=" * 40)
    
    # Check API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health", timeout=10.0)
            health_data = response.json()
            
            print(f"✅ Pipeline API: {health_data['status']}")
            print(f"   Database: {health_data['database']['status']}")
            print(f"   Pipelines: {health_data['database']['pipeline_count']}")
            print(f"   Chroma: {'enabled' if health_data['database']['chroma_enabled'] else 'disabled'}")
            
    except Exception as e:
        print(f"❌ Pipeline API: Error - {str(e)}")
    
    # Check Redis (if enabled)
    try:
        import redis
        r = redis.Redis.from_url("redis://localhost:6379")
        r.ping()
        print("✅ Redis: Connected")
    except Exception as e:
        print(f"⚠️ Redis: {str(e)}")
    
    print("\n🏁 Health check completed")


# scripts/backup.py - Database backup script  
def backup_database(database_url: str = None, backup_path: str = None):
    """Backup database"""
    import subprocess
    from datetime import datetime
    
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///pipeline_codes.db")
    
    if backup_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backup_pipeline_codes_{timestamp}"
    
    print(f"📦 Creating database backup...")
    print(f"Source: {database_url}")
    print(f"Backup: {backup_path}")
    
    try:
        if database_url.startswith("sqlite"):
            # SQLite backup
            import shutil
            db_file = database_url.replace("sqlite:///", "")
            shutil.copy2(db_file, f"{backup_path}.db")
            print(f"✅ SQLite backup created: {backup_path}.db")
            
        elif database_url.startswith("postgresql"):
            # PostgreSQL backup
            result = subprocess.run([
                "pg_dump", database_url, "-f", f"{backup_path}.sql"
            ], capture_output=True, text=True, check=True)
            print(f"✅ PostgreSQL backup created: {backup_path}.sql")
            
        else:
            print("❌ Unsupported database type for backup")
            
    except Exception as e:
        print(f"❌ Backup failed: {str(e)}")


# scripts/restore.py - Database restore script
def restore_database(backup_path: str, database_url: str = None):
    """Restore database from backup"""
    import subprocess
    
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///pipeline_codes.db")
    
    print(f"📂 Restoring database...")
    print(f"Backup: {backup_path}")
    print(f"Target: {database_url}")
    
    try:
        if database_url.startswith("sqlite") and backup_path.endswith(".db"):
            # SQLite restore
            import shutil
            db_file = database_url.replace("sqlite:///", "")
            shutil.copy2(backup_path, db_file)
            print(f"✅ SQLite restore completed")
            
        elif database_url.startswith("postgresql") and backup_path.endswith(".sql"):
            # PostgreSQL restore
            result = subprocess.run([
                "psql", database_url, "-f", backup_path
            ], capture_output=True, text=True, check=True)
            print(f"✅ PostgreSQL restore completed")
            
        else:
            print("❌ Incompatible backup file and database type")
            
    except Exception as e:
        print(f"❌ Restore failed: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "health":
            asyncio.run(check_service_health())
        elif command == "backup":
            backup_path = sys.argv[2] if len(sys.argv) > 2 else None
            backup_database(backup_path=backup_path)
        elif command == "restore":
            if len(sys.argv) < 3:
                print("Usage: python setup.py restore <backup_file>")
                sys.exit(1)
            restore_database(sys.argv[2])
        else:
            print("Unknown command. Use: health, backup, or restore")
    else:
        asyncio.run(main())


# Save init_db.sql content to file
def save_init_sql():
    """Save the PostgreSQL initialization script"""
    init_sql_path = Path("scripts/init_db.sql")
    init_sql_path.parent.mkdir(exist_ok=True)
    
    with open(init_sql_path, 'w') as f:
        f.write(INIT_DB_SQL.strip())
    
    print(f"✅ Saved PostgreSQL init script to {init_sql_path}")


if __name__ == "__main__":
    # Save the SQL file when this script is run
    save_init_sql()