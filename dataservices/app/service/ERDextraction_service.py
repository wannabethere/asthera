
import asyncio
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
import motor.motor_asyncio
from google.cloud import bigquery

# Async SQL drivers
import asyncpg  # PostgreSQL
import aiomysql  # MySQL
#import aioodbc  # SQL Server/Azure SQL


# Fallback to sync SQLAlchemy for unsupported databases
from sqlalchemy import inspect, create_engine




class ERDExtractor:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def get_RDBMS_Extractor(self, connectionDetails):
        database_type = connectionDetails.data_source.database_type.lower()

        # Handle non-SQL databases separately
        if database_type == "mongodb":
            return await self.get_mongodb_schema(connectionDetails)
        elif database_type == "bigquery":
            return await self.get_bigquery_schema(connectionDetails)
        
        # Handle SQL databases with native async drivers
        try:
            schema = await self._extract_sql_schema_async(connectionDetails, database_type)
        except Exception as e:
            print(f"Async extraction failed for {database_type}: {e}")
            # Fallback to sync SQLAlchemy
            schema = await self._extract_sql_schema_sync(connectionDetails, database_type)

        return await self.generate_reactflow_json(schema)

    async def _extract_sql_schema_async(self, connectionDetails, database_type):
        """Extract schema using native async drivers"""
        conn_details = connectionDetails.connection_details
        
        if database_type == "postgresql":
            return await self._extract_postgresql_schema(conn_details)
        elif database_type == "mysql":
            return await self._extract_mysql_schema(conn_details)
        elif database_type == "snowflake":
            return await self._extract_snowflake_schema(conn_details)
        else:
            raise ValueError(f"No async driver available for {database_type}")

    """
    elif database_type in ["sqlserver", "azuresql"]:
                return await self._extract_sqlserver_schema(conn_details)
    """


    async def _extract_postgresql_schema(self, conn_details):
        """Extract PostgreSQL schema using asyncpg"""
        connection = await asyncpg.connect(
            host=conn_details['host'],
            port=conn_details['port'],
            user=conn_details['username'],
            password=conn_details['password'],
            database=conn_details['database']
        )
        
        schema = {"tables": [], "relations": []}
        
        try:
            # Get all tables
            tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """
            tables = await connection.fetch(tables_query)
            
            for table_row in tables:
                table_name = table_row['table_name']
                
                # Get columns
                columns_query = """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1 AND table_schema = 'public'
                    ORDER BY ordinal_position
                """
                columns = await connection.fetch(columns_query, table_name)
                
                # Get primary keys
                pk_query = """
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = $1 
                    AND tc.constraint_type = 'PRIMARY KEY'
                """
                primary_keys = await connection.fetch(pk_query, table_name)
                
                # Get foreign keys
                fk_query = """
                    SELECT 
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu 
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.table_name = $1 
                    AND tc.constraint_type = 'FOREIGN KEY'
                """
                foreign_keys = await connection.fetch(fk_query, table_name)
                
                # Format columns
                formatted_columns = [
                    {
                        "fieldName": col['column_name'],
                        "dataType": col['data_type'],
                    }
                    for col in columns
                ]
                
                schema["tables"].append({
                    "table_name": table_name,
                    "columns": formatted_columns,
                    "primary_key": [pk['column_name'] for pk in primary_keys],
                })
                
                # Add foreign key relationships
                for fk in foreign_keys:
                    schema["relations"].append({
                        "from_table": table_name,
                        "from_column": fk['column_name'],
                        "to_table": fk['foreign_table_name'],
                        "to_column": fk['foreign_column_name'],
                    })
                    
        finally:
            await connection.close()
            
        return schema

    async def _extract_mysql_schema(self, conn_details):
        """Extract MySQL schema using aiomysql"""
        connection = await aiomysql.connect(
            host=conn_details['host'],
            port=conn_details['port'],
            user=conn_details['username'],
            password=conn_details['password'],
            db=conn_details['database']
        )
        
        schema = {"tables": [], "relations": []}
        
        try:
            async with connection.cursor() as cursor:
                # Get all tables
                await cursor.execute("SHOW TABLES")
                tables = await cursor.fetchall()
                
                for (table_name,) in tables:
                    # Get columns
                    await cursor.execute(f"DESCRIBE {table_name}")
                    columns = await cursor.fetchall()
                    
                    # Get foreign keys
                    fk_query = """
                        SELECT 
                            COLUMN_NAME,
                            REFERENCED_TABLE_NAME,
                            REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s 
                        AND TABLE_NAME = %s 
                        AND REFERENCED_TABLE_NAME IS NOT NULL
                    """
                    await cursor.execute(fk_query, (conn_details['database'], table_name))
                    foreign_keys = await cursor.fetchall()
                    
                    # Format columns
                    formatted_columns = []
                    primary_keys = []
                    
                    for col in columns:
                        field_name = col[0]  # Field
                        data_type = col[1]   # Type
                        key_type = col[3]    # Key
                        
                        formatted_columns.append({
                            "fieldName": field_name,
                            "dataType": data_type.split('(')[0],  # Remove size info
                        })
                        
                        if key_type == 'PRI':
                            primary_keys.append(field_name)
                    
                    schema["tables"].append({
                        "table_name": table_name,
                        "columns": formatted_columns,
                        "primary_key": primary_keys,
                    })
                    
                    # Add foreign key relationships
                    for fk in foreign_keys:
                        schema["relations"].append({
                            "from_table": table_name,
                            "from_column": fk[0],
                            "to_table": fk[1],
                            "to_column": fk[2],
                        })
                        
        finally:
            await connection.ensure_closed()
            
        return schema


    async def _extract_sqlserver_schema(self, conn_details):
        """Extract SQL Server/Azure SQL schema using aioodbc"""
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
        
        connection = await aioodbc.connect(dsn=connection_string)
        schema = {"tables": [], "relations": []}
        
        try:
            async with connection.cursor() as cursor:
                # Get all tables
                tables_query = """
                    SELECT TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE'
                """
                await cursor.execute(tables_query)
                tables = await cursor.fetchall()
                
                for (table_name,) in tables:
                    # Get columns
                    columns_query = """
                        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME = ?
                        ORDER BY ORDINAL_POSITION
                    """
                    await cursor.execute(columns_query, table_name)
                    columns = await cursor.fetchall()
                    
                    # Get primary keys
                    pk_query = """
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_NAME = ? 
                        AND CONSTRAINT_NAME LIKE 'PK_%'
                    """
                    await cursor.execute(pk_query, table_name)
                    primary_keys = await cursor.fetchall()
                    
                    # Get foreign keys
                    fk_query = """
                        SELECT 
                            kcu.COLUMN_NAME,
                            kcu2.TABLE_NAME AS REFERENCED_TABLE_NAME,
                            kcu2.COLUMN_NAME AS REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                            ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2
                            ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME
                        WHERE kcu.TABLE_NAME = ?
                    """
                    await cursor.execute(fk_query, table_name)
                    foreign_keys = await cursor.fetchall()
                    
                    # Format columns
                    formatted_columns = [
                        {
                            "fieldName": col[0],
                            "dataType": col[1],
                        }
                        for col in columns
                    ]
                    
                    schema["tables"].append({
                        "table_name": table_name,
                        "columns": formatted_columns,
                        "primary_key": [pk[0] for pk in primary_keys],
                    })
                    
                    # Add foreign key relationships
                    for fk in foreign_keys:
                        schema["relations"].append({
                            "from_table": table_name,
                            "from_column": fk[0],
                            "to_table": fk[1],
                            "to_column": fk[2],
                        })
                        
        finally:
            await connection.close()
            
        return schema

    async def _extract_snowflake_schema(self, conn_details):
        """Extract Snowflake schema - fallback to sync for now"""
        # Snowflake doesn't have mature async support yet
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self._extract_snowflake_schema_sync, conn_details
        )

    def _extract_snowflake_schema_sync(self, conn_details):
        """Sync Snowflake schema extraction"""
        import snowflake.connector
        
        connection = snowflake.connector.connect(
            user=conn_details['username'],
            password=conn_details['password'],
            account=conn_details['account'],
            warehouse=conn_details.get('warehouse'),
            database=conn_details['database'],
            schema=conn_details.get('schema', 'PUBLIC')
        )
        
        schema = {"tables": [], "relations": []}
        
        try:
            cursor = connection.cursor()
            
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for table_row in tables:
                table_name = table_row[1]  # Table name is in second column
                
                # Get columns
                cursor.execute(f"DESCRIBE TABLE {table_name}")
                columns = cursor.fetchall()
                
                # Format columns
                formatted_columns = [
                    {
                        "fieldName": col[0],  # Column name
                        "dataType": col[1],   # Data type
                    }
                    for col in columns
                ]
                
                # Snowflake doesn't have traditional primary keys by default
                # You might need to query constraints separately
                
                schema["tables"].append({
                    "table_name": table_name,
                    "columns": formatted_columns,
                    "primary_key": [],  # Would need additional logic
                })
                
        finally:
            connection.close()
            
        return schema

    async def _extract_sql_schema_sync(self, connectionDetails, database_type):
        """Fallback to sync SQLAlchemy for unsupported databases"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self._extract_sql_schema_sync_blocking, connectionDetails, database_type
        )

    def _extract_sql_schema_sync_blocking(self, connectionDetails, database_type):
        """Blocking SQLAlchemy operations - runs in thread pool"""
        # Map database types to SQLAlchemy dialects
        dialect_map = {
            "postgresql": "postgresql+psycopg2",
            "mysql": "mysql+pymysql",
            "sqlserver": "mssql+pyodbc",
            "azuresql": "mssql+pyodbc",
            "snowflake": "snowflake",
            "oracle": "oracle+oracledb"
        }
        
        dialect = dialect_map.get(database_type, "sqlite")
        connectionString = self._build_connection_string_sync(dialect, connectionDetails, database_type)
        
        engine = create_engine(connectionString, echo=True)
        insp = inspect(engine)
        schema = {"tables": [], "relations": []}

        # Get schema name for databases that support it
        schema_name = None
        if database_type in ["snowflake", "oracle"]:
            schema_name = connectionDetails.connection_details.get("schema")

        # Get table names
        table_names = (
            insp.get_table_names(schema=schema_name)
            if schema_name
            else insp.get_table_names()
        )

        for table in table_names:
            columns = (
                insp.get_columns(table, schema=schema_name)
                if schema_name
                else insp.get_columns(table)
            )
            pk = (
                insp.get_pk_constraint(table, schema=schema_name)
                if schema_name
                else insp.get_pk_constraint(table)
            )
            fks = (
                insp.get_foreign_keys(table, schema=schema_name)
                if schema_name
                else insp.get_foreign_keys(table)
            )

            schema["tables"].append({
                "table_name": table,
                "columns": [
                    {
                        "fieldName": col["name"],
                        "dataType": str(col["type"]).replace("()", ""),
                    }
                    for col in columns
                ],
                "primary_key": pk["constrained_columns"] if pk else [],
            })

            for fk in fks:
                schema["relations"].append({
                    "from_table": table,
                    "from_column": (
                        fk["constrained_columns"][0]
                        if fk["constrained_columns"]
                        else ""
                    ),
                    "to_table": fk["referred_table"],
                    "to_column": (
                        fk["referred_columns"][0] if fk["referred_columns"] else ""
                    ),
                })

        engine.dispose()
        return schema

    def _build_connection_string_sync(self, dialect, connectionDetails, database_type):
        """Build connection string for sync operations"""
        conn_details = connectionDetails.connection_details

        if database_type == "snowflake":
            account = conn_details.get("account", "")
            warehouse = conn_details.get("warehouse", "")
            role = conn_details.get("role", "")

            connectionString = (
                f"{dialect}://{conn_details['username']}:"
                f"{quote_plus(conn_details['password'])}@"
                f"{account}/"
                f"{conn_details['database']}"
            )

            params = []
            if warehouse:
                params.append(f"warehouse={warehouse}")
            if role:
                params.append(f"role={role}")
            if conn_details.get("schema"):
                params.append(f"schema={conn_details['schema']}")

            if params:
                connectionString += "?" + "&".join(params)

        elif database_type == "oracle":
            service_name = conn_details.get(
                "service_name", conn_details.get("database", "")
            )
            connectionString = (
                f"{dialect}://{conn_details['username']}:"
                f"{quote_plus(conn_details['password'])}@"
                f"{conn_details['host']}:"
                f"{conn_details['port']}/"
                f"{service_name}"
            )

        elif database_type in ["azuresql", "sqlserver"]:
            driver = conn_details.get("driver", "ODBC Driver 17 for SQL Server")
            connectionString = (
                f"{dialect}://{conn_details['username']}:"
                f"{quote_plus(conn_details['password'])}@"
                f"{conn_details['host']}:"
                f"{conn_details['port']}/"
                f"{conn_details['database']}?"
                f"driver={quote_plus(driver)}"
            )

        else:
            connectionString = (
                f"{dialect}://{conn_details['username']}:"
                f"{quote_plus(conn_details['password'])}@"
                f"{conn_details['host']}:"
                f"{conn_details['port']}/"
                f"{conn_details['database']}"
            )

        return connectionString

    async def get_mongodb_schema(self, connectionDetails):
        """Extract schema from MongoDB using async driver"""
        conn_details = connectionDetails.connection_details

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
        schema = {"tables": [], "relations": []}

        try:
            collections = await db.list_collection_names()

            for collection_name in collections:
                collection = db[collection_name]
                sample_docs = []
                async for doc in collection.find().limit(100):
                    sample_docs.append(doc)

                fields = set()
                for doc in sample_docs:
                    fields.update(self.get_mongodb_fields(doc))

                schema["tables"].append({
                    "table_name": collection_name,
                    "columns": [{"fieldName": field, "dataType": "Mixed"} for field in fields],
                    "primary_key": ["_id"],
                })

        finally:
            client.close()

        return await self.generate_reactflow_json(schema)

    def get_mongodb_fields(self, doc, prefix=""):
        """Recursively extract field names from MongoDB document"""
        fields = set()
        for key, value in doc.items():
            field_name = f"{prefix}.{key}" if prefix else key
            fields.add(field_name)
            if isinstance(value, dict):
                fields.update(self.get_mongodb_fields(value, field_name))
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                fields.update(self.get_mongodb_fields(value[0], field_name))
        return fields

    async def get_bigquery_schema(self, connectionDetails):
        """Extract schema from BigQuery"""
        conn_details = connectionDetails.connection_details
        schema = await asyncio.get_event_loop().run_in_executor(
            self.executor, self._extract_bigquery_schema, conn_details
        )
        return await self.generate_reactflow_json(schema)

    def _extract_bigquery_schema(self, conn_details):
        """Blocking BigQuery operations"""
        project_id = conn_details.get("project_id")
        dataset_id = conn_details.get("dataset_id")

        client = bigquery.Client(project=project_id)
        schema = {"tables": [], "relations": []}

        dataset_ref = client.dataset(dataset_id)
        dataset = client.get_dataset(dataset_ref)
        tables = client.list_tables(dataset)

        for table_ref in tables:
            table = client.get_table(table_ref)
            columns = []

            for field in table.schema:
                columns.append({
                    "fieldName": field.name,
                    "dataType": field.field_type
                })

            schema["tables"].append({
                "table_name": table.table_id,
                "columns": columns,
                "primary_key": [],
            })

        return schema

    async def generate_reactflow_json(self, schema):
        """Generate ReactFlow JSON"""
        result = {"tables": [], "relationships": []}

        foreign_keys = {}
        for relation in schema.get("relations", []):
            from_table = relation["from_table"]
            from_column = relation["from_column"]
            if from_table not in foreign_keys:
                foreign_keys[from_table] = []
            foreign_keys[from_table].append(from_column)

        start_x = 50
        start_y = 50
        table_width = 280
        table_height = 200
        horizontal_spacing = 100
        vertical_spacing = 80
        tables_per_row = 3

        for index, table in enumerate(schema["tables"]):
            table_name = table["table_name"]
            primary_keys = table.get("primary_key", [])
            table_foreign_keys = foreign_keys.get(table_name, [])

            formatted_columns = []
            for col in table["columns"]:
                field_name = col["fieldName"]
                data_type = col["dataType"]
                is_primary = field_name in primary_keys
                is_foreign = field_name in table_foreign_keys

                symbols = ""
                if is_primary:
                    symbols += " [PK]"
                if is_foreign:
                    symbols += " [FK]"

                formatted_col = f"{field_name} ({data_type}){symbols}"
                formatted_columns.append(formatted_col)

            row = index // tables_per_row
            col = index % tables_per_row
            position_x = start_x + col * (table_width + horizontal_spacing)
            position_y = start_y + row * (table_height + vertical_spacing)

            result["tables"].append({
                "name": table_name,
                "columns": formatted_columns,
                "position": {"x": position_x, "y": position_y},
            })

        for relation in schema.get("relations", []):
            result["relationships"].append({
                "sourceTable": relation["from_table"],
                "targetTable": relation["to_table"],
                "sourceColumn": relation["from_column"],
                "targetColumn": relation["to_column"],
                "description": relation.get(
                    "description",
                    f"{relation['from_table']} relates to {relation['to_table']}",
                ),
            })

        return result

    def __del__(self):
        """Clean up thread pool executor"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)