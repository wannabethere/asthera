import json
import sys
from typing import Dict, Any, Tuple
import logging
from app.service.models import connection_details
import traceback
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_postgres_connection(config: connection_details) -> Tuple[bool, str]:
    """Test PostgreSQL database connection"""
    try:
        import asyncpg

        conn = await asyncpg.connect(
            host=config.database_details["host"],
            port=config.database_details["port"],
            user=config.database_details["username"],
            password=config.database_details["password"],
            database=config.database_details["database"],
        )
        await conn.close()
        return True, "PostgreSQL connection successful"
    except ImportError:
        return (
            False,
            "asyncpg library not installed. Install with: pip install asyncpg",
        )
    except Exception as e:
        logger.error("PostgreSQL connection failed", exc_info=True)
        return False, f"PostgreSQL connection failed: {str(e)}"


async def test_mysql_connection(config: connection_details) -> Tuple[bool, str]:
    """Test MySQL database connection"""
    try:
        import aiomysql

        conn = await aiomysql.connect(
            host=config.database_details["host"],
            port=config.database_details["port"],
            user=config.database_details["username"],
            password=config.database_details["password"],
            db=config.database_details["database"],
        )
        await conn.close()
        return True, "MySQL connection successful"
    except ImportError:
        return (
            False,
            "aiomysql library not installed. Install with: pip install aiomysql",
        )
    except Exception as e:
        logger.error("MySQL connection failed", exc_info=True)
        return False, f"MySQL connection failed: {str(e)}"


async def test_sqlserver_connection(config: connection_details) -> Tuple[bool, str]:
    """Test SQL Server database connection"""
    try:
        import pyodbc

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config.database_details['host']},{config.database_details['port']};"
            f"DATABASE={config.database_details['database']};"
            f"UID={config.database_details['username']};"
            f"PWD={config.database_details['password']}"
        )
        # pyodbc does not support async, use sync call inside thread executor
        loop = asyncio.get_event_loop()
        def connect_sync():
            conn = pyodbc.connect(conn_str)
            conn.close()
        await loop.run_in_executor(None, connect_sync)

        return True, "SQL Server connection successful"
    except ImportError:
        return False, "pyodbc library not installed. Install with: pip install pyodbc"
    except Exception as e:
        logger.error("SQL Server connection failed", exc_info=True)
        return False, f"SQL Server connection failed: {str(e)}"


async def test_mongodb_connection(config: connection_details) -> Tuple[bool, str]:
    """Test MongoDB database connection"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(
            host=config.database_details["host"],
            port=config.database_details["port"],
            username=config.database_details["username"],
            password=config.database_details["password"],
            authSource=config.database_details.get("authSource", "admin"),
        )
        # Test the connection with async ping
        await client.admin.command("ping")
        client.close()
        return True, "MongoDB connection successful"
    except ImportError:
        return False, "motor library not installed. Install with: pip install motor"
    except Exception as e:
        logger.error("MongoDB connection failed", exc_info=True)
        return False, f"MongoDB connection failed: {str(e)}"


async def test_oracle_connection(config: connection_details) -> Tuple[bool, str]:
    """Test Oracle database connection"""
    try:
        import oracledb

        d = config.database_details
        loop = asyncio.get_event_loop()

        def connect_sync():
            user = d["username"]
            password = d["password"]
            host = d["host"]
            port = d["port"]
            service_name = d.get("service_name") or d.get("database")
            sid = d.get("sid")
            if service_name:
                conn = oracledb.connect(
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    service_name=service_name,
                )
            elif sid:
                dsn = oracledb.makedsn(host, port, sid=sid)
                conn = oracledb.connect(user=user, password=password, dsn=dsn)
            else:
                raise ValueError(
                    "Oracle database_details must include service_name, database, or sid"
                )
            conn.close()

        await loop.run_in_executor(None, connect_sync)

        return True, "Oracle connection successful"
    except ImportError:
        return (
            False,
            "oracledb library not installed. Install with: pip install oracledb",
        )
    except Exception as e:
        logger.error("Oracle connection failed", exc_info=True)
        return False, f"Oracle connection failed: {str(e)}"


async def test_azuresql_connection(config: connection_details) -> Tuple[bool, str]:
    """Test Azure SQL database connection"""
    try:
        import pyodbc

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER=tcp:{config.database_details['server']},{config.database_details['port']};"
            f"DATABASE={config.database_details['database']};"
            f"UID={config.database_details['username']};"
            f"PWD={config.database_details['password']};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
        loop = asyncio.get_event_loop()

        def connect_sync():
            conn = pyodbc.connect(conn_str)
            conn.close()

        await loop.run_in_executor(None, connect_sync)

        return True, "Azure SQL connection successful"
    except ImportError:
        return False, "pyodbc library not installed. Install with: pip install pyodbc"
    except Exception as e:
        logger.error("Azure SQL connection failed", exc_info=True)
        return False, f"Azure SQL connection failed: {str(e)}"


async def test_bigquery_connection(config: connection_details) -> Tuple[bool, str]:
    """Test BigQuery connection"""
    try:
        from google.cloud import bigquery
        import os
        import functools
        import concurrent.futures

        # Set credentials if path is provided
        if "credentialsPath" in config.database_details:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.database_details[
                "credentialsPath"
            ]

        client = bigquery.Client(project=config.database_details["projectId"])

        loop = asyncio.get_event_loop()

        # Run blocking query in executor to keep async interface
        def run_query():
            query = "SELECT 1 as test_connection"
            client.query(query).result()

        await loop.run_in_executor(None, run_query)

        return True, "BigQuery connection successful"
    except ImportError:
        return (
            False,
            "google-cloud-bigquery library not installed. Install with: pip install google-cloud-bigquery",
        )
    except Exception as e:
        logger.error("BigQuery connection failed", exc_info=True)
        return False, f"BigQuery connection failed: {str(e)}"


async def test_snowflake_connection(config: connection_details) -> Tuple[bool, str]:
    """Test Snowflake connection"""
    try:
        import snowflake.connector
        import functools

        loop = asyncio.get_event_loop()

        def connect_sync():
            conn = snowflake.connector.connect(
                user=config.database_details["username"],
                password=config.database_details["password"],
                account=config.database_details["account"],
                warehouse=config.database_details["warehouse"],
                database=config.database_details["database"],
                schema=config.database_details["schema"],
                role=config.database_details.get("role"),
            )
            conn.close()

        await loop.run_in_executor(None, connect_sync)

        return True, "Snowflake connection successful"
    except ImportError:
        return (
            False,
            "snowflake-connector-python library not installed. Install with: pip install snowflake-connector-python",
        )
    except Exception as e:
        logger.error("Snowflake connection failed", exc_info=True)
        return False, f"Snowflake connection failed: {str(e)}"


async def test_database_connection(db_config: connection_details) -> Tuple[bool, str]:
    """Test database connection based on database type"""
    logger.info("Starting test_database_connection")
    db_type = db_config.database_type.lower()
    logger.info(f"Database type: {db_type}")
    connection_testers = {
        "postgresql": test_postgres_connection,
        "mysql": test_mysql_connection,
        "sqlserver": test_sqlserver_connection,
        "mongodb": test_mongodb_connection,
        "oracle": test_oracle_connection,
        "azuresql": test_azuresql_connection,
        "bigquery": test_bigquery_connection,
        "snowflake": test_snowflake_connection,
    }

    if db_type not in connection_testers:
        logger.error(f"Unsupported database type: {db_type}")
        return False, f"Unsupported database type: {db_type}"

    return await connection_testers[db_type](db_config)
