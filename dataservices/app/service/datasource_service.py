from app.schemas.dbmodels import DataSources, ConnectionDetails
from sqlalchemy.orm import joinedload
from app.service.dbconnection_service import test_database_connection
from app.service.models import connection_details
from datetime import datetime
from app.service.ERDextraction_service import ERDExtractor
from sqlalchemy.ext.asyncio import AsyncSession
import traceback
from typing import Dict,List
from sqlalchemy import select, func,delete
import asyncio
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
import json


import asyncpg
import aiomysql
#import aioodbc
import motor.motor_asyncio


import pymongo
from google.cloud import bigquery
import snowflake.connector
import cx_Oracle
from sqlalchemy import create_engine, text

class DataSourceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_data_source(self, name: str, database_type: str, required_details: Dict):
        """Create a new data source"""
        try:
            data_source = DataSources(
                name=name,
                database_type=database_type,
                required_details=required_details,
            )
            self.session.add(data_source)
            await self.session.commit()
            await self.session.refresh(data_source)
            return data_source
        except Exception as e:
            print("=="*10)
            traceback.print_exc()
            print("Error Ended ====")
            await self.session.rollback()
            raise e
        finally:
            await self.session.close()

    async def bulk_create_data_sources(self, data_sources_list: List):
        """Create multiple data sources at once"""
        created_sources = []
        try:
            for source_data in data_sources_list:
                data_source = DataSources(
                    name=source_data["name"],
                    database_type=source_data["database_type"],
                    required_details=source_data["required_details"],
                )
                self.session.add(data_source)
                created_sources.append(data_source)

            await self.session.commit()
            for source in created_sources:
                await self.session.refresh(source)
            return created_sources
        except Exception as e:
            print("================Error Occured ================")
            traceback.print_exc()
            print("================Error Ended ================")
            await self.session.rollback()
            raise e
        finally:
            await self.session.close()

    async def populate_default_data_sources(self):
        """Populate the database with default data source configurations"""
        # Define the data source configurations
        data_sources_config = [
            {
                "name": "PostgreSQL",
                "database_type": "postgresql",
                "required_details": {
                    "host": "localhost",
                    "port": 5432,
                    "username": "your_username",
                    "password": "your_password",
                    "database": "your_database_name",
                    "connectionString": "postgresql://your_username:your_password@localhost:5432/your_database_name",
                },
            },
            {
                "name": "MySQL",
                "database_type": "mysql",
                "required_details": {
                    "host": "localhost",
                    "port": 3306,
                    "username": "your_username",
                    "password": "your_password",
                    "database": "your_database_name",
                    "connectionString": "mysql://your_username:your_password@localhost:3306/your_database_name",
                },
            },
            {
                "name": "MongoDB",
                "database_type": "mongodb",
                "required_details": {
                    "host": "localhost",
                    "port": 27017,
                    "username": "your_username",
                    "password": "your_password",
                    "database": "your_database_name",
                    "authSource": "admin",
                    "connectionString": "mongodb://your_username:your_password@localhost:27017/your_database_name?authSource=admin",
                },
            },
            {
                "name": "Oracle",
                "database_type": "oracle",
                "required_details": {
                    "host": "localhost",
                    "port": 1521,
                    "username": "your_username",
                    "password": "your_password",
                    "sid": "your_sid",
                    "connectionString": "oracle+cx_oracle://your_username:your_password@localhost:1521/?service_name=your_sid",
                },
            },
            {
                "name": "Azure SQL",
                "database_type": "azuresql",
                "required_details": {
                    "server": "your_server.database.windows.net",
                    "port": 1433,
                    "username": "your_username",
                    "password": "your_password",
                    "database": "your_database",
                    "encrypt": True,
                    "connectionString": "Server=tcp:your_server.database.windows.net,1433;Initial Catalog=your_database;Persist Security Info=False;User ID=your_username;Password=your_password;MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;",
                },
            },
            {
                "name": "BigQuery",
                "database_type": "bigquery",
                "required_details": {
                    "projectId": "your_project_id",
                    "credentialsPath": "/path/to/your/service-account.json",
                    "dataset": "your_dataset",
                    "connectionString": "bigquery://your_project_id/your_dataset?credentials_path=/path/to/your/service-account.json",
                },
            },
            {
                "name": "Snowflake",
                "database_type": "snowflake",
                "required_details": {
                    "account": "your_account_id",
                    "username": "your_username",
                    "password": "your_password",
                    "warehouse": "your_warehouse",
                    "database": "your_database",
                    "schema": "your_schema",
                    "role": "your_role",
                    "connectionString": "snowflake://your_username:your_password@your_account_id.snowflakecomputing.com/?warehouse=your_warehouse&db=your_database&schema=your_schema&role=your_role",
                },
            },
        ]
        """
        {
                "name": "SQL Server",
                "database_type": "sqlserver",
                "required_details": {
                    "host": "localhost",
                    "port": 1433,
                    "username": "your_username",
                    "password": "your_password",
                    "database": "your_database_name",
                    "connectionString": "mssql://your_username:your_password@localhost:1433/your_database_name",
                },
            },
        """
        # Check if data sources already exist to avoid duplicates
        try:
            result = await self.session.execute(select(func.count()).select_from(DataSources))
            existing_count = result.scalar_one()
            if existing_count > 0:
                print(
                    f"Data sources already exist ({existing_count} records). Skipping population."
                )
                return

            # Create all data sources
            created_sources = await self.bulk_create_data_sources(data_sources_config)
            print(
                f"Successfully created {len(created_sources)} data source configurations:"
            )
            for source in created_sources:
                print(f"  - {source.name} ({source.database_type})")

            return created_sources

        except Exception as e:
            print(f"Error populating data sources: {e}")
            print("================Error Occured ================")
            traceback.print_exc()
            print("================Error Ended ================")
            raise e
        finally:
            await self.session.close()

    async def clear_all_data_sources(self):
        """Clear all data sources (use with caution!)"""
        try:
            deleted_count = await self.session.execute(delete(DataSources))
            await self.session.commit()
            print(f"Deleted {deleted_count} data source records.")
            return deleted_count.rowcount
        except Exception as e:
            print(f"Error populating data sources: {e}")
            print("================Error Occured ================")
            traceback.print_exc()
            print("================Error Ended ================")
            await self.session.rollback()
            raise e
        finally:
            await self.session.close()

    async def create_connection_details(self, data_source_id: str, connection_details: dict):
        """Create connection details for a data source"""
        try:
            conn_details = ConnectionDetails(
                data_source_id=data_source_id, connection_details=connection_details
            )
            self.session.add(conn_details)
            await self.session.commit()
            await self.session.refresh(conn_details)
            return conn_details
        except Exception as e:
            print(f"Error populating data sources: {e}")
            print("================Error Occured ================")
            traceback.print_exc()
            print("================Error Ended ================")
            await self.session.rollback()
            raise e
        finally:
            await self.session.close()

    async def get_all_data_sources(self):
        """Get all active data sources"""
        try:
            result = await self.session.execute(select(DataSources))
            datasources = result.scalars().all()
            return datasources
        except Exception as e:
            print(f"Error populating data sources: {e}")
            print("================Error Occured ================")
            traceback.print_exc()
            print("================Error Ended ================")
            
        finally:
            await self.session.close()


class ConnectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validateConnection(self, connection_details: connection_details):
        print("Connection Details in Validate Connection",connection_details)
        try:
            connection_tester = await test_database_connection(connection_details)
            if connection_tester[0]:
                print("in if")
                return True
            return False
        except Exception as e:
            print(f"Error populating data sources: {e}")
            print("================Error Occured ================")
            traceback.print_exc()
            print("================Error Ended ================")
            print(e)
            return False

    async def create_connection(self, connection_details: connection_details,user_id):
        connection_tester = await self.validateConnection(connection_details)
        if not connection_tester:
            return {"Message": "Connection Failed"}
        connection_details = connection_details.model_dump()
        datasource = await(
            self.db.execute(select(DataSources)
            .filter(DataSources.database_type == connection_details["database_type"])
            
        ))
        datasource = datasource.scalar_one_or_none()
        if not datasource:
            return {"Message": "Data Source Not Found"}
        connection_details["data_source_id"] = datasource.id
        connection = ConnectionDetails(
            data_source_id=datasource.id,
            connection_details=connection_details["database_details"],
            name=connection_details["name"],
            is_active=True,
            last_tested=datetime.now(),
            test_status="success",
            created_by=user_id,
            updated_by=user_id
        )

        self.db.add(connection)
        await self.db.commit()
        
        return {
            "Message": "Connection Created Successfully",
            "connection_id": connection.id,
            "connection_name": connection.name,
            "database_type": connection.data_source.database_type,
            "data_source_id": connection.data_source_id,
            "connection_details": {
                "host": connection.connection_details["host"],
                "port": connection.connection_details["port"],
                "type": "database",
            },
            "created_by": connection.created_by,
            "updated_by": connection.updated_by
        }

    async def get_all_connections(self,user_id):

        connections = await self.db.execute(select(ConnectionDetails).filter(ConnectionDetails.is_active == True).filter(ConnectionDetails.created_by==user_id))
        return connections.scalars().all()

    async def get_ERD_By_ConnectionID(self, connectionId,user_id):
        """
        Generate ERD data by redirecting to appropriate extraction method based on database type
        """
        connectionDetails = await (
            self.db.execute(select(ConnectionDetails)
            .options(joinedload(ConnectionDetails.data_source))
            .filter(ConnectionDetails.id == connectionId)
            .filter(ConnectionDetails.created_by==user_id)
           
        ))
        connectionDetails = connectionDetails.scalar_one_or_none()

        if not connectionDetails:
            raise ValueError("DataSource Connection not found")

        extractor = ERDExtractor()
        database_type = connectionDetails.data_source.database_type.lower()

        if database_type in [
            "postgresql",
            "mysql",
            "sqlserver",
            "azuresql",
            "snowflake",
            "oracle",
        ]:

            return await extractor.get_RDBMS_Extractor(connectionDetails)

        elif database_type == "mongodb":

            return await extractor.get_mongodb_schema(connectionDetails)

        elif database_type == "bigquery":

            return await extractor.get_bigquery_schema(connectionDetails)

        else:
            raise ValueError(f"Unsupported database type: {database_type}")





class DataRetriever:
    def __init__(self,db:AsyncSession):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.db=db

    async def get_data_from_connection(self, connection_id: str, tables: List[str]) -> Dict[str, Any]:
        """
        Retrieve data from specified tables across different database types
        
        Args:
            connection_id: Database connection identifier
            tables: List of table names to retrieve data from
            
        Returns:
            Dictionary with table names as keys and data as values
        """
        # Get connection details from database
        connection = await self.db.execute(
            select(ConnectionDetails).options(joinedload(ConnectionDetails.data_source)).where(ConnectionDetails.id == connection_id)
        )
        connection = connection.unique().scalar_one_or_none()
        
        if not connection:
            raise ValueError("Connection is not found")
        print("Connection",connection)
        database_type = connection.data_source.database_type.lower()
        
        # Route to appropriate database handler
        if database_type == "postgresql":
            return await self._get_postgresql_data(connection, tables)
        elif database_type == "mysql":
            return await self._get_mysql_data(connection, tables)
        elif database_type == "mongodb":
            return await self._get_mongodb_data(connection, tables)
        elif database_type == "oracle":
            return await self._get_oracle_data(connection, tables)
        elif database_type == "bigquery":
            return await self._get_bigquery_data(connection, tables)
        elif database_type == "snowflake":
            return await self._get_snowflake_data(connection, tables)
        else:
            raise ValueError(f"Unsupported database type: {database_type}")
    """
    elif database_type in ["sqlserver", "azuresql"]:
            return await self._get_sqlserver_data(connection, tables)
    """

    async def _get_postgresql_data(self, connection, tables: List[str]) -> Dict[str, Any]:
        """Retrieve data from PostgreSQL using asyncpg"""
        conn_details = connection.connection_details
        
        db_connection = await asyncpg.connect(
            host=conn_details['host'],
            port=conn_details['port'],
            user=conn_details['username'],
            password=conn_details['password'],
            database=conn_details['database']
        )
        
        result = {}
        
        try:
            for table in tables:
                try:
                    # Get table data with limit to avoid memory issues
                    query = f"SELECT * FROM {table} LIMIT 250"
                    rows = await db_connection.fetch(query)
                    
                    # Convert to list of dictionaries
                    table_data = [dict(row) for row in rows]
                    result[table] = {
                        'data': table_data,
                        'row_count': len(table_data),
                        'columns': list(rows[0].keys()) if rows else []
                    }
                    
                except Exception as e:
                    result[table] = {
                        'error': str(e),
                        'data': [],
                        'row_count': 0,
                        'columns': []
                    }
                    
        finally:
            await db_connection.close()
            
        return result
    
    async def _get_mysql_data(self, connection, tables: List[str]) -> Dict[str, Any]:
        """Retrieve data from MySQL using aiomysql"""
        conn_details = connection.connection_details
        
        db_connection = await aiomysql.connect(
            host=conn_details['host'],
            port=conn_details['port'],
            user=conn_details['username'],
            password=conn_details['password'],
            db=conn_details['database']
        )
        
        result = {}
        
        try:
            async with db_connection.cursor(aiomysql.DictCursor) as cursor:
                for table in tables:
                    try:
                        # Get table data with limit
                        query = f"SELECT * FROM {table} LIMIT 250"
                        await cursor.execute(query)
                        rows = await cursor.fetchall()
                        
                        result[table] = {
                            'data': rows,
                            'row_count': len(rows),
                            'columns': [desc[0] for desc in cursor.description] if cursor.description else []
                        }
                        
                    except Exception as e:
                        result[table] = {
                            'error': str(e),
                            'data': [],
                            'row_count': 0,
                            'columns': []
                        }
                        
        finally:
            await db_connection.ensure_closed()
            
        return result

    async def _get_sqlserver_data(self, connection, tables: List[str]) -> Dict[str, Any]:
        """Retrieve data from SQL Server/Azure SQL using aioodbc"""
        conn_details = connection.connection_details
        driver = conn_details.get("driver", "ODBC Driver 17 for SQL Server")
        
        connection_string = (
            f"Driver={{{driver}}};"
            f"Server={conn_details['host']},{conn_details['port']};"
            f"Database={conn_details['database']};"
            f"Uid={conn_details['username']};"
            f"Pwd={conn_details['password']};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
        
        db_connection = await aioodbc.connect(dsn=connection_string)
        result = {}
        
        try:
            async with db_connection.cursor() as cursor:
                for table in tables:
                    try:
                        # Get table data with limit
                        query = f"SELECT TOP 250 * FROM {table}"
                        await cursor.execute(query)
                        rows = await cursor.fetchall()
                        
                        # Get column names
                        columns = [desc[0] for desc in cursor.description] if cursor.description else []
                        
                        # Convert rows to dictionaries
                        table_data = []
                        for row in rows:
                            row_dict = {}
                            for i, value in enumerate(row):
                                row_dict[columns[i]] = value
                            table_data.append(row_dict)
                        
                        result[table] = {
                            'data': table_data,
                            'row_count': len(table_data),
                            'columns': columns
                        }
                        
                    except Exception as e:
                        result[table] = {
                            'error': str(e),
                            'data': [],
                            'row_count': 0,
                            'columns': []
                        }
                        
        finally:
            await db_connection.close()
            
        return result

    async def _get_mongodb_data(self, connection, tables: List[str]) -> Dict[str, Any]:
        """Retrieve data from MongoDB using motor"""
        conn_details = connection.connection_details
        
        # Build MongoDB connection string
        if "username" in conn_details and "password" in conn_details:
            connection_string = (
                f"mongodb://{conn_details['username']}:"
                f"{quote_plus(conn_details['password'])}@"
                f"{conn_details['host']}:"
                f"{conn_details['port']}/"
                f"{conn_details['database']}"
            )
        else:
            connection_string = (
                f"mongodb://{conn_details['host']}:{conn_details['port']}"
            )
        
        client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        db = client[conn_details["database"]]
        result = {}
        
        try:
            for collection_name in tables:
                try:
                    collection = db[collection_name]
                    
                    # Get documents with limit
                    documents = []
                    async for doc in collection.find().limit(250):
                        # Convert ObjectId to string for JSON serialization
                        if '_id' in doc:
                            doc['_id'] = str(doc['_id'])
                        documents.append(doc)
                    
                    # Get unique field names
                    columns = set()
                    for doc in documents:
                        columns.update(doc.keys())
                    
                    result[collection_name] = {
                        'data': documents,
                        'row_count': len(documents),
                        'columns': list(columns)
                    }
                    
                except Exception as e:
                    result[collection_name] = {
                        'error': str(e),
                        'data': [],
                        'row_count': 0,
                        'columns': []
                    }
                    
        finally:
            client.close()
            
        return result

    async def _get_oracle_data(self, connection, tables: List[str]) -> Dict[str, Any]:
        """Retrieve data from Oracle using cx_Oracle in thread pool"""
        conn_details = connection.connection_details
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self._get_oracle_data_sync, conn_details, tables
        )

    def _get_oracle_data_sync(self, conn_details: Dict, tables: List[str]) -> Dict[str, Any]:
        """Synchronous Oracle data retrieval"""
        # Oracle connection string
        dsn = cx_Oracle.makedsn(
            conn_details['host'],
            conn_details['port'],
            service_name=conn_details.get('service_name', conn_details['database'])
        )
        
        db_connection = cx_Oracle.connect(
            user=conn_details['username'],
            password=conn_details['password'],
            dsn=dsn
        )
        
        result = {}
        
        try:
            cursor = db_connection.cursor()
            
            for table in tables:
                try:
                    # Get table data with limit
                    query = f"SELECT * FROM {table} WHERE ROWNUM <= 250"
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    
                    # Get column names
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    
                    # Convert to dictionaries
                    table_data = []
                    for row in rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            row_dict[columns[i]] = value
                        table_data.append(row_dict)
                    
                    result[table] = {
                        'data': table_data,
                        'row_count': len(table_data),
                        'columns': columns
                    }
                    
                except Exception as e:
                    result[table] = {
                        'error': str(e),
                        'data': [],
                        'row_count': 0,
                        'columns': []
                    }
                    
        finally:
            db_connection.close()
            
        return result

    async def _get_bigquery_data(self, connection, tables: List[str]) -> Dict[str, Any]:
        """Retrieve data from BigQuery using google-cloud-bigquery in thread pool"""
        conn_details = connection.connection_details
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self._get_bigquery_data_sync, conn_details, tables
        )

    def _get_bigquery_data_sync(self, conn_details: Dict, tables: List[str]) -> Dict[str, Any]:
        """Synchronous BigQuery data retrieval"""
        project_id = conn_details.get("project_id")
        dataset_id = conn_details.get("dataset_id")
        
        client = bigquery.Client(project=project_id)
        result = {}
        
        for table in tables:
            try:
                # Query with limit
                query = f"""
                    SELECT * 
                    FROM `{project_id}.{dataset_id}.{table}` 
                    LIMIT 250
                """
                
                query_job = client.query(query)
                rows = query_job.result()
                
                # Convert to list of dictionaries
                table_data = []
                columns = []
                
                for row in rows:
                    if not columns:
                        columns = list(row.keys())
                    table_data.append(dict(row))
                
                result[table] = {
                    'data': table_data,
                    'row_count': len(table_data),
                    'columns': columns
                }
                
            except Exception as e:
                result[table] = {
                    'error': str(e),
                    'data': [],
                    'row_count': 0,
                    'columns': []
                }
                
        return result

    async def _get_snowflake_data(self, connection, tables: List[str]) -> Dict[str, Any]:
        """Retrieve data from Snowflake using snowflake-connector-python in thread pool"""
        conn_details = connection.connection_details
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self._get_snowflake_data_sync, conn_details, tables
        )

    def _get_snowflake_data_sync(self, conn_details: Dict, tables: List[str]) -> Dict[str, Any]:
        """Synchronous Snowflake data retrieval"""
        db_connection = snowflake.connector.connect(
            user=conn_details['username'],
            password=conn_details['password'],
            account=conn_details['account'],
            warehouse=conn_details.get('warehouse'),
            database=conn_details['database'],
            schema=conn_details.get('schema', 'PUBLIC')
        )
        
        result = {}
        
        try:
            cursor = db_connection.cursor()
            
            for table in tables:
                try:
                    # Get table data with limit
                    query = f"SELECT * FROM {table} LIMIT 250"
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    
                    # Get column names
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    
                    # Convert to dictionaries
                    table_data = []
                    for row in rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            row_dict[columns[i]] = value
                        table_data.append(row_dict)
                    
                    result[table] = {
                        'data': table_data,
                        'row_count': len(table_data),
                        'columns': columns
                    }
                    
                except Exception as e:
                    result[table] = {
                        'error': str(e),
                        'data': [],
                        'row_count': 0,
                        'columns': []
                    }
                    
        finally:
            db_connection.close()
            
        return result

    def __del__(self):
        """Clean up thread pool executor"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)

