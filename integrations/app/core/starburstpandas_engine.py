import logging
import pandas as pd
import sqlparse
from typing import Any, Dict, Optional, Tuple, Union
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
from .engine import Engine, clean_generation_result, add_quotes
from app.utils.cache import Cache, InMemoryCache

# Optional Trino/Starburst imports
try:
    import trino
    from trino.auth import BasicAuthentication, JWTAuthentication, CertificateAuthentication, OAuth2Authentication
    from trino.exceptions import TrinoException
    TRINO_AVAILABLE = True
except ImportError:
    TRINO_AVAILABLE = False

# Optional SQLAlchemy for Trino
try:
    from sqlalchemy import create_engine as sqlalchemy_create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

logger = logging.getLogger("starburst-pandas-engine")


class StarburstPandasEngine(Engine):
    """
    Dedicated PandasEngine for Trino/Starburst connections with comprehensive authentication support
    """
    
    def __init__(
        self,
        host: str,
        user: str,
        catalog: str,
        schema: str = 'default',
        port: int = 443,
        auth_type: str = 'basic',
        # Basic/LDAP Authentication
        username: str = None,
        password: str = None,
        # JWT Authentication
        jwt_token: str = None,
        # Certificate Authentication
        cert_path: str = None,
        key_path: str = None,
        # OAuth2 Authentication
        oauth2_config: Dict[str, Any] = None,
        # Kerberos Authentication
        kerberos_config: Dict[str, Any] = None,
        # Connection settings
        http_scheme: str = 'https',
        verify: bool = True,
        request_timeout: int = 30,
        # Session settings
        session_properties: Dict[str, str] = None,
        client_info: str = 'starburst-pandas-engine',
        client_tags: list = None,
        roles: Dict[str, str] = None,
        timezone: str = None,
        # Engine settings
        use_sqlalchemy: bool = False,
        local_data_sources: Dict[str, pd.DataFrame] = None,
        cache_provider: Optional[Cache] = None,
        cache_ttl: int = 3600
    ):
        """
        Initialize StarburstPandasEngine
        
        Args:
            host: Starburst/Trino cluster host
            user: Username for connection
            catalog: Default catalog to use
            schema: Default schema to use (default: 'default')
            port: Port number (default: 443 for HTTPS, 8080 for HTTP)
            auth_type: Authentication type ('basic', 'jwt', 'certificate', 'oauth2', 'kerberos', 'ldap')
            username: Username for basic/LDAP authentication
            password: Password for basic/LDAP authentication
            jwt_token: JWT token for JWT authentication
            cert_path: Certificate file path for certificate authentication
            key_path: Private key file path for certificate authentication
            oauth2_config: OAuth2 configuration dictionary
            kerberos_config: Kerberos configuration dictionary
            http_scheme: HTTP scheme ('https' or 'http')
            verify: Verify SSL certificates (default: True)
            request_timeout: Request timeout in seconds (default: 30)
            session_properties: Session properties dictionary
            client_info: Client information string
            client_tags: List of client tags
            roles: Roles mapping dictionary
            timezone: Session timezone
            use_sqlalchemy: Use SQLAlchemy for connections (alternative to direct trino client)
            local_data_sources: Optional local pandas DataFrames for hybrid queries
            cache_provider: Cache provider instance
            cache_ttl: Cache TTL in seconds
        """
        if not TRINO_AVAILABLE:
            raise ImportError(
                "Trino client not available. Install with: pip install trino"
            )
        
        # Connection parameters
        self.host = host
        self.port = port
        self.user = user
        self.catalog = catalog
        self.schema = schema
        self.auth_type = auth_type
        self.username = username
        self.password = password
        self.jwt_token = jwt_token
        self.cert_path = cert_path
        self.key_path = key_path
        self.oauth2_config = oauth2_config or {}
        self.kerberos_config = kerberos_config or {}
        self.http_scheme = http_scheme
        self.verify = verify
        self.request_timeout = request_timeout
        
        # Session parameters
        self.session_properties = session_properties or {}
        self.client_info = client_info
        self.client_tags = client_tags or []
        self.roles = roles or {}
        self.timezone = timezone
        
        # Engine settings
        self.use_sqlalchemy = use_sqlalchemy and SQLALCHEMY_AVAILABLE
        self.local_data_sources = local_data_sources or {}
        
        # Connection objects
        self._trino_connection = None
        self._sqlalchemy_engine = None
        
        # Threading and caching
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.cache_provider = cache_provider or InMemoryCache()
        self.cache_ttl = cache_ttl
        
        # Initialize connections
        self._setup_connections()
    
    def _setup_connections(self):
        """Setup Trino connections"""
        try:
            # Setup authentication
            auth = self._setup_authentication()
            
            # Setup direct Trino connection
            self._trino_connection = trino.dbapi.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                catalog=self.catalog,
                schema=self.schema,
                auth=auth,
                http_scheme=self.http_scheme,
                verify=self.verify,
                request_timeout=self.request_timeout,
                session_properties=self.session_properties,
                client_info=self.client_info,
                client_tags=self.client_tags,
                roles=self.roles,
                timezone=self.timezone
            )
            
            # Test connection
            cursor = self._trino_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            logger.info(f"Trino connection established to {self.host}:{self.port}")
            
            # Setup SQLAlchemy connection if requested
            if self.use_sqlalchemy:
                self._setup_sqlalchemy_connection(auth)
                
        except Exception as e:
            logger.error(f"Failed to setup Trino connection: {e}")
            raise
    
    def _setup_authentication(self):
        """Setup Trino authentication based on configuration"""
        if self.auth_type == 'basic' or self.auth_type == 'ldap':
            if not self.username or not self.password:
                raise ValueError("Username and password required for basic/LDAP authentication")
            return BasicAuthentication(self.username, self.password)
        
        elif self.auth_type == 'jwt':
            if not self.jwt_token:
                raise ValueError("JWT token required for JWT authentication")
            return JWTAuthentication(self.jwt_token)
        
        elif self.auth_type == 'certificate':
            if not self.cert_path or not self.key_path:
                raise ValueError("Certificate and key paths required for certificate authentication")
            return CertificateAuthentication(self.cert_path, self.key_path)
        
        elif self.auth_type == 'oauth2':
            return OAuth2Authentication(**self.oauth2_config)
        
        elif self.auth_type == 'kerberos':
            try:
                from trino.auth import KerberosAuthentication
                return KerberosAuthentication(**self.kerberos_config)
            except ImportError:
                raise ImportError("Kerberos authentication requires additional dependencies")
        
        else:
            # No authentication
            return None
    
    def _setup_sqlalchemy_connection(self, auth):
        """Setup SQLAlchemy connection for Trino"""
        try:
            if not SQLALCHEMY_AVAILABLE:
                logger.warning("SQLAlchemy not available, skipping SQLAlchemy setup")
                return
            
            # Build connection string for Trino
            if self.auth_type == 'basic' or self.auth_type == 'ldap':
                connection_string = (
                    f"trino://{self.username}:{self.password}@"
                    f"{self.host}:{self.port}/"
                    f"{self.catalog}/{self.schema}"
                    f"?http_scheme={self.http_scheme}"
                )
            else:
                connection_string = (
                    f"trino://{self.user}@"
                    f"{self.host}:{self.port}/"
                    f"{self.catalog}/{self.schema}"
                    f"?http_scheme={self.http_scheme}"
                )
            
            self._sqlalchemy_engine = sqlalchemy_create_engine(
                connection_string,
                pool_pre_ping=True
            )
            
            # Test SQLAlchemy connection
            with self._sqlalchemy_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("SQLAlchemy Trino connection established")
            
        except Exception as e:
            logger.warning(f"Failed to setup SQLAlchemy connection: {e}")
            self._sqlalchemy_engine = None
    
    def add_local_data_source(self, table_name: str, dataframe: pd.DataFrame):
        """Add a local pandas DataFrame as a data source"""
        self.local_data_sources[table_name] = dataframe
        # Clear cache when data sources change
        asyncio.create_task(self.clear_cache())
    
    def _execute_trino_query_direct(self, sql: str) -> Optional[pd.DataFrame]:
        """Execute query using direct Trino connection"""
        if not self._trino_connection:
            return None
        
        try:
            cursor = self._trino_connection.cursor()
            cursor.execute(sql)
            
            # Fetch all results
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            cursor.close()
            
            # Create DataFrame
            if rows:
                df = pd.DataFrame(rows, columns=columns)
            else:
                df = pd.DataFrame(columns=columns)
            
            return df
            
        except TrinoException as e:
            logger.warning(f"Trino query failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"Trino query failed with unexpected error: {e}")
            return None
    
    def _execute_trino_query_sqlalchemy(self, sql: str) -> Optional[pd.DataFrame]:
        """Execute query using SQLAlchemy Trino connection"""
        if not self._sqlalchemy_engine:
            return None
        
        try:
            return pd.read_sql_query(sql, self._sqlalchemy_engine)
        except Exception as e:
            logger.warning(f"SQLAlchemy Trino query failed: {e}")
            return None
    
    def _parse_and_validate_sql(self, sql: str, limit: Optional[int] = None) -> str:
        """Parse and validate SQL query, apply limit if needed"""
        # Clean the SQL
        cleaned_sql = clean_generation_result(sql)
        
        # Add quotes if needed
        quoted_sql, error = add_quotes(cleaned_sql)
        if error:
            logger.warning(f"Failed to add quotes: {error}, using original SQL")
            quoted_sql = cleaned_sql
        
        # Apply limit if specified
        if limit is not None:
            sql_upper = quoted_sql.upper()
            if 'LIMIT' not in sql_upper:
                quoted_sql = f"{quoted_sql.rstrip(';')} LIMIT {limit}"
        
        return quoted_sql
    
    def _execute_sql_sync(self, sql: str, limit: Optional[int] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Synchronous SQL execution"""
        try:
            # Parse and validate SQL
            quoted_sql = self._parse_and_validate_sql(sql, limit)
            
            result_df = None
            
            # Try SQLAlchemy first if enabled
            if self.use_sqlalchemy and self._sqlalchemy_engine:
                result_df = self._execute_trino_query_sqlalchemy(quoted_sql)
            
            # Fall back to direct connection
            if result_df is None:
                result_df = self._execute_trino_query_direct(quoted_sql)
            
            # If query fails, return error
            if result_df is None:
                return False, {
                    "error": "Failed to execute query on Starburst/Trino cluster",
                    "data": [],
                    "columns": []
                }
            
            # Check if SQL already has LIMIT clause (for pagination)
            sql_upper = quoted_sql.upper()
            has_limit_or_offset = 'LIMIT' in sql_upper or 'OFFSET' in sql_upper
            
            # Only apply additional limit if no LIMIT/OFFSET is present in the SQL
            if not has_limit_or_offset and limit is not None:
                result_df = result_df.iloc[:limit]
            
            # Format and return result
            return True, self._convert_to_json_serializable(result_df)
            
        except Exception as e:
            logger.exception(f"Error executing SQL: {e}")
            return False, {
                "error": str(e),
                "data": [],
                "columns": []
            }
    
    def _generate_cache_key(self, sql: str, limit: Optional[int] = None, **kwargs) -> str:
        """Generate a unique cache key for the SQL query and parameters"""
        # Create a string representation of all parameters
        params_str = f"sql:{sql}|limit:{limit}|host:{self.host}|catalog:{self.catalog}|schema:{self.schema}"
        
        # Add any additional kwargs that might affect the result
        for key, value in sorted(kwargs.items()):
            params_str += f"|{key}:{value}"
        
        # Generate hash for consistent key length
        return hashlib.md5(params_str.encode()).hexdigest()
    
    async def execute_sql(
        self,
        sql: str,
        session: aiohttp.ClientSession,
        dry_run: bool = True,
        limit: Optional[int] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Execute SQL query asynchronously with caching support
        
        Args:
            sql: SQL query to execute
            session: aiohttp ClientSession (not used in this engine)
            dry_run: If True, validates SQL without executing
            limit: Optional limit for number of rows returned
            use_cache: Whether to use caching (default: True)
            **kwargs: Additional arguments
            
        Returns:
            Tuple of (success: bool, result: Dict)
        """
        try:
            if dry_run:
                # For dry run, just validate the SQL syntax
                try:
                    sqlparse.parse(sql)
                    return True, {"status": "SQL syntax is valid"}
                except Exception as e:
                    return False, {"error": f"SQL syntax error: {str(e)}"}
            
            # Check if SQL already has LIMIT clause
            sql_upper = sql.upper()
            has_limit = 'LIMIT' in sql_upper
            
            # Only add default limit if no LIMIT clause is present and no specific limit is provided
            if not has_limit and limit is None:
                limit = 1000
                sql = f"{sql} LIMIT {limit}"
            elif limit is not None and not has_limit:
                # Use provided limit
                sql = f"{sql} LIMIT {limit}"
            
            # Check cache if enabled
            if use_cache:
                cache_key = self._generate_cache_key(sql, limit, **kwargs)
                cached_result = await self.cache_provider.get(cache_key)
                
                if cached_result is not None:
                    logger.info(f"Cache hit for query: {sql[:100]}...")
                    return True, cached_result
                else:
                    logger.info(f"Cache miss for query: {sql[:100]}...")
            
            # Execute SQL in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            success, result = await loop.run_in_executor(
                self.executor,
                self._execute_sql_sync,
                sql,
                limit
            )
            
            # Cache the result if execution was successful and caching is enabled
            if success and use_cache and result:
                cache_key = self._generate_cache_key(sql, limit, **kwargs)
                await self.cache_provider.set(cache_key, result, ttl=self.cache_ttl)
                logger.info(f"Cached result for query: {sql[:100]}...")
            
            return success, result
            
        except Exception as e:
            logger.exception(f"Error in execute_sql: {e}")
            return False, {"error": str(e), "data": [], "columns": []}
    
    async def execute_sql_in_batches(
        self,
        sql: str,
        session: aiohttp.ClientSession,
        batch_size: int = 1000,
        batch_num: Optional[int] = None,
        max_batches: Optional[int] = None,
        dry_run: bool = True,
        use_cache: bool = True,
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Execute SQL query in batches to handle large result sets efficiently
        
        Args:
            sql: SQL query to execute
            session: aiohttp ClientSession (not used)
            batch_size: Number of rows to fetch in each batch
            batch_num: Specific batch number to retrieve (None for all batches)
            max_batches: Maximum number of batches to process (None for unlimited)
            dry_run: If True, validates SQL without executing
            use_cache: Whether to use caching (default: True)
            **kwargs: Additional arguments
            
        Returns:
            Tuple of (success: bool, result: Dict)
        """
        try:
            if dry_run:
                try:
                    sqlparse.parse(sql)
                    return True, {"status": "SQL syntax is valid"}
                except Exception as e:
                    return False, {"error": f"SQL syntax error: {str(e)}"}
            
            # Check cache for batch operations if enabled
            if use_cache:
                cache_key = self._generate_cache_key(
                    sql,
                    limit=None,
                    batch_size=batch_size,
                    batch_num=batch_num,
                    max_batches=max_batches,
                    **kwargs
                )
                cached_result = await self.cache_provider.get(cache_key)
                
                if cached_result is not None:
                    logger.info(f"Cache hit for batch query: {sql[:100]}...")
                    return True, cached_result
                else:
                    logger.info(f"Cache miss for batch query: {sql[:100]}...")
            
            # First, get total count
            count_sql = f"SELECT COUNT(*) as total_count FROM ({sql}) as count_query"
            success, count_result = await self.execute_sql(
                count_sql,
                session,
                dry_run=False,
                use_cache=use_cache,
                **kwargs
            )
            
            if not success or not count_result.get("data"):
                return False, {"error": "Failed to get total count", "data": [], "columns": []}
            
            total_count = int(count_result["data"][0]["total_count"])
            
            # Calculate number of batches
            num_batches = (total_count + int(batch_size) - 1) // int(batch_size)
            if max_batches is not None:
                num_batches = min(num_batches, max_batches)
            
            # If batch_num is specified, only process that batch
            if batch_num is not None:
                if batch_num < 0 or batch_num >= num_batches:
                    return False, {
                        "error": f"Invalid batch number. Must be between 0 and {num_batches - 1}",
                        "data": [],
                        "columns": []
                    }
                
                offset = batch_num * batch_size
                batch_sql = f"{sql} LIMIT {batch_size} OFFSET {offset}"
                
                success, batch_result = await self.execute_sql(
                    batch_sql,
                    session,
                    dry_run=False,
                    use_cache=use_cache,
                    **kwargs
                )
                
                if not success:
                    return False, {
                        "error": f"Failed to execute batch {batch_num}",
                        "data": [],
                        "columns": []
                    }
                
                result = {
                    "data": batch_result.get("data", []),
                    "columns": batch_result.get("columns", []),
                    "row_count": len(batch_result.get("data", [])),
                    "batch_info": {
                        "batch_num": batch_num,
                        "batch_size": batch_size,
                        "total_batches": num_batches,
                        "total_count": total_count,
                        "is_last_batch": batch_num == num_batches - 1
                    }
                }
                
                # Cache the result if enabled
                if use_cache:
                    cache_key = self._generate_cache_key(
                        sql,
                        limit=None,
                        batch_size=batch_size,
                        batch_num=batch_num,
                        max_batches=max_batches,
                        **kwargs
                    )
                    await self.cache_provider.set(cache_key, result, ttl=self.cache_ttl)
                
                return True, result
            
            # Process all batches if no specific batch requested
            all_data = []
            columns = None
            
            for current_batch in range(num_batches):
                offset = current_batch * batch_size
                batch_sql = f"{sql} LIMIT {batch_size} OFFSET {offset}"
                
                success, batch_result = await self.execute_sql(
                    batch_sql,
                    session,
                    dry_run=False,
                    use_cache=use_cache,
                    **kwargs
                )
                
                if not success:
                    return False, {
                        "error": f"Failed to execute batch {current_batch + 1}",
                        "data": all_data,
                        "columns": columns
                    }
                
                # Store columns from first batch
                if columns is None and batch_result.get("columns"):
                    columns = batch_result["columns"]
                
                # Append batch data
                if batch_result.get("data"):
                    all_data.extend(batch_result["data"])
                
                # Log progress
                logger.info(f"Processed batch {current_batch + 1}/{num_batches} ({len(all_data)}/{total_count} rows)")
            
            result = {
                "data": all_data,
                "columns": columns,
                "row_count": len(all_data),
                "total_count": total_count,
                "batches_processed": num_batches,
                "batch_size": batch_size
            }
            
            # Cache the result if enabled
            if use_cache:
                cache_key = self._generate_cache_key(
                    sql,
                    limit=None,
                    batch_size=batch_size,
                    batch_num=batch_num,
                    max_batches=max_batches,
                    **kwargs
                )
                await self.cache_provider.set(cache_key, result, ttl=self.cache_ttl)
            
            return True, result
            
        except Exception as e:
            logger.exception(f"Error in execute_sql_in_batches: {e}")
            return False, {"error": str(e), "data": [], "columns": []}
    
    def get_table_info(self, table_name: str, catalog: str = None, schema: str = None) -> Dict[str, Any]:
        """Get information about a table"""
        catalog = catalog or self.catalog
        schema = schema or self.schema
        
        try:
            # Query table structure from Trino
            query = f"""
            SELECT 
                column_name,
                data_type,
                is_nullable
            FROM {catalog}.information_schema.columns 
            WHERE table_catalog = '{catalog}'
              AND table_schema = '{schema}'
              AND table_name = '{table_name}'
            ORDER BY ordinal_position
            """
            
            cursor = self._trino_connection.cursor()
            cursor.execute(query)
            columns_result = cursor.fetchall()
            columns_cols = [desc[0] for desc in cursor.description]
            cursor.close()
            
            if columns_result:
                columns_df = pd.DataFrame(columns_result, columns=columns_cols)
                
                # Get row count
                cursor = self._trino_connection.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {catalog}.{schema}.{table_name}")
                row_count = cursor.fetchone()[0]
                cursor.close()
                
                return {
                    "name": table_name,
                    "catalog": catalog,
                    "schema": schema,
                    "source": "starburst_trino",
                    "columns": [
                        {
                            "name": row['column_name'],
                            "type": row['data_type'],
                            "nullable": row['is_nullable'] == 'YES'
                        }
                        for _, row in columns_df.iterrows()
                    ],
                    "row_count": row_count
                }
            else:
                return {"error": f"Table {catalog}.{schema}.{table_name} not found"}
                
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            return {"error": f"Failed to get table info: {str(e)}"}
    
    def get_available_tables(self, catalog: str = None, schema: str = None) -> list[str]:
        """Get list of available table names"""
        catalog = catalog or self.catalog
        schema = schema or self.schema
        
        try:
            cursor = self._trino_connection.cursor()
            cursor.execute(f"SHOW TABLES FROM {catalog}.{schema}")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return sorted(tables)
        except Exception as e:
            logger.warning(f"Failed to get tables: {e}")
            return []
    
    def get_available_catalogs(self) -> list[str]:
        """Get list of available catalogs"""
        try:
            cursor = self._trino_connection.cursor()
            cursor.execute("SHOW CATALOGS")
            catalogs = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return sorted(catalogs)
        except Exception as e:
            logger.warning(f"Failed to get catalogs: {e}")
            return []
    
    def get_available_schemas(self, catalog: str = None) -> list[str]:
        """Get list of available schemas"""
        catalog = catalog or self.catalog
        
        try:
            cursor = self._trino_connection.cursor()
            cursor.execute(f"SHOW SCHEMAS FROM {catalog}")
            schemas = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return sorted(schemas)
        except Exception as e:
            logger.warning(f"Failed to get schemas: {e}")
            return []
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster information"""
        try:
            cursor = self._trino_connection.cursor()
            cursor.execute("SELECT * FROM system.runtime.nodes")
            nodes = cursor.fetchall()
            node_columns = [desc[0] for desc in cursor.description]
            cursor.close()
            
            nodes_df = pd.DataFrame(nodes, columns=node_columns)
            
            return {
                "host": self.host,
                "port": self.port,
                "catalog": self.catalog,
                "schema": self.schema,
                "auth_type": self.auth_type,
                "node_count": len(nodes_df),
                "nodes": nodes_df.to_dict('records') if len(nodes_df) <= 10 else f"{len(nodes_df)} nodes"
            }
        except Exception as e:
            logger.warning(f"Failed to get cluster info: {e}")
            return {
                "host": self.host,
                "port": self.port,
                "catalog": self.catalog,
                "schema": self.schema,
                "auth_type": self.auth_type,
                "error": str(e)
            }
    
    async def clear_cache(self):
        """Clear all cached results"""
        await self.cache_provider.clear()
        logger.info("Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if hasattr(self.cache_provider, '_cache'):
            cache_size = len(self.cache_provider._cache)
            return {
                "cache_type": type(self.cache_provider).__name__,
                "cache_size": cache_size,
                "cache_ttl": self.cache_ttl
            }
        return {
            "cache_type": type(self.cache_provider).__name__,
            "cache_ttl": self.cache_ttl
        }
    
    def _convert_to_json_serializable(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Convert DataFrame to JSON-serializable format"""
        try:
            # Create a copy to avoid modifying the original DataFrame
            df_copy = df.copy()
            
            # Convert problematic data types to strings
            for column in df_copy.columns:
                try:
                    dtype = df_copy[column].dtype
                    dtype_str = str(dtype).lower()
                    
                    # Handle different data types
                    if 'timedelta' in dtype_str:
                        df_copy[column] = df_copy[column].astype(str)
                    elif 'datetime' in dtype_str:
                        df_copy[column] = df_copy[column].dt.strftime('%Y-%m-%d %H:%M:%S')
                    elif 'categorical' in dtype_str:
                        df_copy[column] = df_copy[column].astype(str)
                    elif 'object' in dtype_str:
                        df_copy[column] = df_copy[column].astype(str).replace('nan', None)
                    elif 'period' in dtype_str:
                        df_copy[column] = df_copy[column].astype(str)
                    elif 'interval' in dtype_str:
                        df_copy[column] = df_copy[column].astype(str)
                    elif 'sparse' in dtype_str:
                        df_copy[column] = df_copy[column].astype(str)
                    elif hasattr(dtype, 'kind') and dtype.kind in ['O', 'S', 'U']:
                        df_copy[column] = df_copy[column].astype(str).replace('nan', None)
                except Exception as e:
                    logger.warning(f"Failed to convert column {column}: {e}")
                    df_copy[column] = df_copy[column].astype(str)
            
            # Convert DataFrame to dictionary
            data = df_copy.to_dict(orient='records')
            columns = df_copy.columns.tolist()
            
            return {
                "data": data,
                "columns": columns,
                "row_count": len(data)
            }
        except Exception as e:
            logger.error(f"Error converting DataFrame to JSON-serializable format: {e}")
            return {
                "data": [],
                "columns": df.columns.tolist() if hasattr(df, 'columns') else [],
                "row_count": len(df) if hasattr(df, '__len__') else 0,
                "error": f"Failed to serialize data: {str(e)}"
            }
    
    def cleanup(self):
        """Clean up resources"""
        if self._trino_connection:
            try:
                self._trino_connection.close()
            except Exception as e:
                logger.warning(f"Error closing Trino connection: {e}")
            self._trino_connection = None
        
        if self._sqlalchemy_engine:
            try:
                self._sqlalchemy_engine.dispose()
            except Exception as e:
                logger.warning(f"Error disposing SQLAlchemy engine: {e}")
            self._sqlalchemy_engine = None
        
        self.executor.shutdown(wait=True)
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self.cleanup()
        except Exception:
            pass


# Configuration and factory classes
class StarburstEngineConfig:
    """Configuration helper for StarburstPandasEngine"""
    
    @staticmethod
    def for_starburst_cloud(
        cluster_url: str,
        username: str,
        password: str,
        catalog: str = 'hive',
        schema: str = 'default',
        **kwargs
    ) -> StarburstPandasEngine:
        """Create engine for Starburst Cloud"""
        # Parse cluster URL
        if cluster_url.startswith('https://'):
            host = cluster_url[8:]
            http_scheme = 'https'
            port = 443
        elif cluster_url.startswith('http://'):
            host = cluster_url[7:]
            http_scheme = 'http'
            port = 8080
        else:
            host = cluster_url
            http_scheme = 'https'
            port = 443
        
        # Remove port from host if specified in URL
        if ':' in host:
            host, port_str = host.split(':')
            port = int(port_str)
        
        return StarburstPandasEngine(
            host=host,
            port=port,
            user=username,
            catalog=catalog,
            schema=schema,
            auth_type='basic',
            username=username,
            password=password,
            http_scheme=http_scheme,
            **kwargs
        )
    
    @staticmethod
    def for_trino_cluster(
        host: str,
        user: str,
        catalog: str,
        schema: str = 'default',
        port: int = 8080,
        http_scheme: str = 'http',
        **kwargs
    ) -> StarburstPandasEngine:
        """Create engine for open-source Trino cluster"""
        return StarburstPandasEngine(
            host=host,
            port=port,
            user=user,
            catalog=catalog,
            schema=schema,
            auth_type=None,  # No auth for open-source Trino
            http_scheme=http_scheme,
            **kwargs
        )
    
    @staticmethod
    def for_jwt_auth(
        host: str,
        user: str,
        catalog: str,
        jwt_token: str,
        schema: str = 'default',
        port: int = 443,
        **kwargs
    ) -> StarburstPandasEngine:
        """Create engine with JWT authentication"""
        return StarburstPandasEngine(
            host=host,
            port=port,
            user=user,
            catalog=catalog,
            schema=schema,
            auth_type='jwt',
            jwt_token=jwt_token,
            **kwargs
        )
    
    @staticmethod
    def for_oauth2(
        host: str,
        user: str,
        catalog: str,
        oauth2_config: Dict[str, Any],
        schema: str = 'default',
        port: int = 443,
        **kwargs
    ) -> StarburstPandasEngine:
        """Create engine with OAuth2 authentication"""
        return StarburstPandasEngine(
            host=host,
            port=port,
            user=user,
            catalog=catalog,
            schema=schema,
            auth_type='oauth2',
            oauth2_config=oauth2_config,
            **kwargs
        )