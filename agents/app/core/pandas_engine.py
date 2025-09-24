import logging
import pandas as pd
import sqlparse
from typing import Any, Dict, Optional, Tuple, Union
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import tempfile
import os
import hashlib
from .engine import Engine, clean_generation_result, add_quotes
from app.settings import EngineType
from app.utils.cache import Cache, InMemoryCache
from app.settings import get_settings
# Optional PostgreSQL imports
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
    import psycopg2
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

# Get settings
settings = get_settings()

# Set OpenAI API key from settings
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
logger = logging.getLogger("lexy-ai-service")


class PandasEngine(Engine):
    def __init__(
        self, 
        engine_type: EngineType = EngineType.PANDAS,
        data_sources: Dict[str, pd.DataFrame] = None, 
        connection_string: str = None,
        postgres_config: Dict[str, str] = None,
        cache_provider: Optional[Cache] = None,
        cache_ttl: int = 3600  # Default 1 hour TTL
    ):
        """
        Initialize PandasEngine
        
        Args:
            data_sources: Dictionary mapping table names to pandas DataFrames
            connection_string: Optional SQLite connection string for persistent storage
            postgres_config: Optional PostgreSQL connection configuration
            cache_provider: Optional cache provider (defaults to InMemoryCache)
            cache_ttl: Cache TTL in seconds (default: 3600)
        """
        self.data_sources = data_sources or {}
        self.connection_string = connection_string
        self.postgres_config = postgres_config
        self._temp_db_path = None
        self._postgres_engine = None
        self.engine_type = engine_type
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Setup cache
        self.cache_provider = cache_provider or InMemoryCache()
        self.cache_ttl = cache_ttl
        
        # Setup PostgreSQL if config provided
        if postgres_config and POSTGRES_AVAILABLE:
            self._setup_postgres_connection()
        
    def add_data_source(self, table_name: str, dataframe: pd.DataFrame):
        """Add a pandas DataFrame as a data source"""
        self.data_sources[table_name] = dataframe
        # Clear cache when data sources change
        asyncio.create_task(self.clear_cache())
        
    def _setup_postgres_connection(self):
        """Setup PostgreSQL connection if config is provided"""
        try:
            host = self.postgres_config.get('host', 'localhost')
            port = self.postgres_config.get('port', '5432')
            database = self.postgres_config.get('database')
            username = self.postgres_config.get('username')
            password = self.postgres_config.get('password')
            
            if not all([database, username, password]):
                raise ValueError("PostgreSQL database, username, and password are required")
            
            connection_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
            self._postgres_engine = create_engine(connection_url, pool_pre_ping=True)
            
            # Test connection
            with self._postgres_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("PostgreSQL connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup PostgreSQL connection: {e}")
            self._postgres_engine = None
        
    def _setup_temp_sqlite(self) -> str:
        """Create a temporary SQLite database and load DataFrames into it"""
        if self._temp_db_path is None:
            # Create temporary database
            temp_fd, self._temp_db_path = tempfile.mkstemp(suffix='.db')
            os.close(temp_fd)
            
            # Load DataFrames into SQLite
            conn = sqlite3.connect(self._temp_db_path)
            for table_name, df in self.data_sources.items():
                df.to_sql(table_name, conn, if_exists='replace', index=False)
            conn.close()
            
        return self._temp_db_path
        
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

    def _format_query_result(self, result_df: pd.DataFrame) -> Dict[str, Any]:
        """Format query result into standard response format"""
        df = convert_to_json_serializable(result_df)
        data = result_df.to_dict(orient='records')
        columns = result_df.columns.tolist()
        
        return {
            "data": data,
            "columns": columns,
            "row_count": len(data)
        }

    def _execute_postgres_query(self, sql: str) -> Optional[pd.DataFrame]:
        """Execute query using PostgreSQL connection"""
        if not self._postgres_engine:
            return None
            
        try:
            # Clean the SQL query to avoid formatting issues
            cleaned_sql = self._clean_sql_for_execution(sql)
            logger.info(f"Executing PostgreSQL query: {cleaned_sql[:100]}...")
            return pd.read_sql_query(cleaned_sql, self._postgres_engine)
        except Exception as e:
            logger.warning(f"PostgreSQL query failed: {e}")
            logger.warning(f"SQL that failed: {sql}")
            return None
    
    def _clean_sql_for_execution(self, sql: str) -> str:
        """Clean SQL query for execution to avoid common issues"""
        if not sql:
            return ""
        
        # Remove leading/trailing whitespace
        sql = sql.strip()
        
        # Replace multiple whitespace characters with single spaces
        import re
        sql = re.sub(r'\s+', ' ', sql)
        
        # Ensure proper spacing around SQL keywords
        sql = re.sub(r'\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|UNION|JOIN|INNER JOIN|LEFT JOIN|RIGHT JOIN|FULL JOIN)\b', r' \1 ', sql, flags=re.IGNORECASE)
        
        # Clean up multiple spaces
        sql = re.sub(r'\s+', ' ', sql)
        
        # Ensure semicolon at the end if not present
        if not sql.endswith(';'):
            sql = sql + ';'
            
        return sql.strip()

    def _execute_sqlite_query(self, sql: str) -> Optional[pd.DataFrame]:
        """Execute query using SQLite connection"""
        if not self.data_sources:
            return None
            
        try:
            db_path = self._setup_temp_sqlite()
            conn = sqlite3.connect(db_path)
            try:
                return pd.read_sql_query(sql, conn)
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"SQLite query failed: {e}")
            return None

    def _execute_df_query(self, sql: str) -> Optional[pd.DataFrame]:
        """Execute SQL query directly on Pandas DataFrames"""
        try:
            # Parse SQL to extract table name and conditions
            parsed = sqlparse.parse(sql)[0]
            tokens = parsed.tokens
            
            # Extract table name, WHERE clause, LIMIT, and OFFSET
            table_name = None
            where_clause = None
            select_columns = []
            limit_value = None
            offset_value = None
            
            # More robust parsing logic
            in_select = False
            in_from = False
            
            for i, token in enumerate(tokens):
                token_str = str(token).strip().upper()
                
                if token_str == 'SELECT':
                    in_select = True
                    in_from = False
                elif token_str == 'FROM':
                    in_select = False
                    in_from = True
                elif token_str == 'WHERE':
                    in_select = False
                    in_from = False
                    where_clause = str(token)
                elif isinstance(token, sqlparse.sql.Limit):
                    # Extract LIMIT value
                    limit_tokens = token.tokens
                    for limit_token in limit_tokens:
                        if isinstance(limit_token, sqlparse.sql.Literal):
                            try:
                                limit_value = int(str(limit_token))
                            except ValueError:
                                logger.warning(f"Invalid LIMIT value: {limit_token}")
                        elif hasattr(limit_token, 'value') and str(limit_token.value).isdigit():
                            try:
                                limit_value = int(str(limit_token.value))
                            except ValueError:
                                logger.warning(f"Invalid LIMIT value: {limit_token.value}")
                        elif str(limit_token).isdigit():
                            try:
                                limit_value = int(str(limit_token))
                            except ValueError:
                                logger.warning(f"Invalid LIMIT value: {limit_token}")
                elif token_str == 'OFFSET':
                    # Extract OFFSET value from next token
                    if i + 1 < len(tokens):
                        next_token = tokens[i + 1]
                        if isinstance(next_token, sqlparse.sql.Literal):
                            try:
                                offset_value = int(str(next_token))
                            except ValueError:
                                logger.warning(f"Invalid OFFSET value: {next_token}")
                        elif hasattr(next_token, 'value'):
                            try:
                                offset_value = int(str(next_token.value))
                            except ValueError:
                                logger.warning(f"Invalid OFFSET value: {next_token.value}")
                        elif str(next_token).isdigit():
                            try:
                                offset_value = int(str(next_token))
                            except ValueError:
                                logger.warning(f"Invalid OFFSET value: {next_token}")
                elif in_from and isinstance(token, sqlparse.sql.Identifier):
                    table_name = token.get_real_name()
                elif in_select and isinstance(token, sqlparse.sql.IdentifierList):
                    select_columns = [str(col).strip() for col in token.get_identifiers()]
                elif in_select and isinstance(token, sqlparse.sql.Identifier) and token.get_name().upper() not in ['SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT', 'OFFSET']:
                    select_columns = [token.get_name()]
            
            if not table_name or table_name not in self.data_sources:
                return None
                
            df = self.data_sources[table_name]
            
            # Handle SELECT * queries
            if not select_columns or (len(select_columns) == 1 and select_columns[0] == '*'):
                result_df = df
            else:
                # Handle specific column selection
                result_df = df[select_columns]
            
            # Apply WHERE clause if present
            if where_clause:
                # Convert SQL WHERE to pandas query
                where_expr = where_clause.replace('WHERE', '').strip()
                # Basic SQL to pandas conversion
                where_expr = where_expr.replace('=', '==')
                where_expr = where_expr.replace('AND', '&')
                where_expr = where_expr.replace('OR', '|')
                where_expr = where_expr.replace('IS NULL', '.isna()')
                where_expr = where_expr.replace('IS NOT NULL', '.notna()')
                
                try:
                    result_df = result_df.query(where_expr)
                except Exception as query_error:
                    logger.warning(f"Pandas query failed: {query_error}")
                    return None
            
            # Apply OFFSET if present
            if offset_value is not None and offset_value > 0:
                if offset_value < len(result_df):
                    result_df = result_df.iloc[offset_value:]
                else:
                    # If offset is beyond the data, return empty DataFrame
                    return pd.DataFrame(columns=result_df.columns)
            
            # Apply LIMIT if present
            if limit_value is not None and limit_value > 0:
                result_df = result_df.iloc[:limit_value]
            
            return result_df
            
        except Exception as e:
            logger.warning(f"DataFrame query execution failed: {e}")
            return None

    def _execute_sql_sync(self, sql: str, limit: Optional[int] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Synchronous SQL execution using pandas"""
        try:
            # Parse and validate SQL
            quoted_sql = self._parse_and_validate_sql(sql, limit)
            
            # Handle engine_type whether it's an enum or string
            engine_type_str = self.engine_type.value if hasattr(self.engine_type, 'value') else str(self.engine_type)
            
            if engine_type_str == 'PANDAS' or self.engine_type == EngineType.PANDAS:
                # Try direct DataFrame execution first
                result_df = self._execute_df_query(quoted_sql)
            elif engine_type_str == 'POSTGRES' or self.engine_type == EngineType.POSTGRES:
                result_df = self._execute_postgres_query(quoted_sql)
            elif engine_type_str == 'SQLITE' or self.engine_type == EngineType.SQLITE:
                result_df = self._execute_sqlite_query(quoted_sql)
            
            # If PostgreSQL fails, try SQLite
            #if result_df is None:
            #    result_df = self._execute_sqlite_query(quoted_sql)
            
            # If all methods fail, return error
            if result_df is None:
                return False, {
                    "error": "Failed to execute query on all available data sources",
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
            return True, convert_to_json_serializable(result_df)
                
        except Exception as e:
            logger.exception(f"Error executing SQL: {e}")
            return False, {
                "error": str(e),
                "data": [],
                "columns": []
            }
    
    def _generate_cache_key(self, sql: str, limit: Optional[int] = None, **kwargs) -> str:
        """Generate a unique cache key for the SQL query and parameters"""
        # Handle engine_type whether it's an enum or string
        engine_type_str = self.engine_type.value if hasattr(self.engine_type, 'value') else str(self.engine_type)
        
        # Create a string representation of all parameters
        params_str = f"sql:{sql}|limit:{limit}|engine:{engine_type_str}"
        
        # Add data source information to ensure cache invalidation when data changes
        data_sources_str = "|".join([f"{name}:{len(df)}" for name, df in self.data_sources.items()])
        params_str += f"|data_sources:{data_sources_str}"
        
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
        Execute SQL query asynchronously using pandas with caching support
        
        Args:
            sql: SQL query to execute
            session: aiohttp ClientSession (not used in pandas engine)
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
            
            # Check if SQL already has LIMIT clause (for pagination)
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
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get information about a table"""
        # First try PostgreSQL if available
        if self._postgres_engine:
            try:
                # Query table structure from PostgreSQL
                query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
                """
                
                columns_df = pd.read_sql_query(
                    query, 
                    self._postgres_engine, 
                    params=[table_name]
                )
                
                if not columns_df.empty:
                    # Get row count
                    count_query = f"SELECT COUNT(*) as row_count FROM {table_name}"
                    count_df = pd.read_sql_query(count_query, self._postgres_engine)
                    row_count = count_df['row_count'].iloc[0]
                    
                    return {
                        "name": table_name,
                        "source": "postgresql",
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
            except Exception as e:
                logger.warning(f"Failed to get PostgreSQL table info: {e}")
        
        # Fallback to DataFrame info
        if table_name not in self.data_sources:
            return {"error": f"Table {table_name} not found"}
            
        df = self.data_sources[table_name]
        return {
            "name": table_name,
            "source": "dataframe",
            "columns": [
                {
                    "name": col,
                    "type": str(df[col].dtype),
                    "nullable": df[col].isnull().any()
                }
                for col in df.columns
            ],
            "row_count": len(df)
        }
    
    def get_available_tables(self) -> list[str]:
        """Get list of available table names"""
        tables = list(self.data_sources.keys())
        
        # Add PostgreSQL tables if available
        if self._postgres_engine:
            try:
                query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                """
                
                pg_tables_df = pd.read_sql_query(query, self._postgres_engine)
                pg_tables = pg_tables_df['table_name'].tolist()
                
                # Combine and deduplicate
                all_tables = list(set(tables + pg_tables))
                return sorted(all_tables)
                
            except Exception as e:
                logger.warning(f"Failed to get PostgreSQL tables: {e}")
        
        return sorted(tables)
    
    def cleanup(self):
        """Clean up temporary resources"""
        if self._temp_db_path and os.path.exists(self._temp_db_path):
            os.unlink(self._temp_db_path)
            self._temp_db_path = None
        
        if self._postgres_engine:
            self._postgres_engine.dispose()
            self._postgres_engine = None
        
        self.executor.shutdown(wait=True)
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.cleanup()

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
        Execute SQL query in batches to handle large result sets efficiently with caching support
        
        Args:
            sql: SQL query to execute
            session: aiohttp ClientSession (not used in pandas engine)
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
                # For dry run, just validate the SQL syntax
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

    async def clear_cache(self):
        """Clear all cached results"""
        await self.cache_provider.clear()
        logger.info("Cache cleared")
    
    async def invalidate_cache_for_table(self, table_name: str):
        """Invalidate cache entries that might be affected by changes to a specific table"""
        # This is a simplified approach - in a more sophisticated implementation,
        # you might want to track which cache keys are associated with which tables
        await self.cache_provider.clear()
        logger.info(f"Cache invalidated for table: {table_name}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics (if supported by the cache provider)"""
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


class PandasEngineConfig:
    """Configuration helper for PandasEngine"""
    
    @staticmethod
    def from_dataframes(
        dataframes: Dict[str, pd.DataFrame], 
        cache_provider: Optional[Cache] = None,
        cache_ttl: int = 3600
    ) -> PandasEngine:
        """Create engine from dictionary of DataFrames"""
        return PandasEngine(
            data_sources=dataframes,
            cache_provider=cache_provider,
            cache_ttl=cache_ttl
        )
    
    @staticmethod
    def from_csv_files(
        csv_files: Dict[str, str],
        cache_provider: Optional[Cache] = None,
        cache_ttl: int = 3600
    ) -> PandasEngine:
        """Create engine from CSV files"""
        dataframes = {}
        for table_name, csv_path in csv_files.items():
            try:
                dataframes[table_name] = pd.read_csv(csv_path)
                logger.info(f"Loaded CSV file: {csv_path} as table: {table_name}")
            except Exception as e:
                logger.error(f"Failed to load CSV file {csv_path}: {e}")
        return PandasEngine(
            data_sources=dataframes,
            cache_provider=cache_provider,
            cache_ttl=cache_ttl
        )
    
    @staticmethod
    def from_excel_file(
        excel_path: str, 
        sheet_names: Dict[str, str] = None,
        cache_provider: Optional[Cache] = None,
        cache_ttl: int = 3600
    ) -> PandasEngine:
        """
        Create engine from Excel file
        
        Args:
            excel_path: Path to Excel file
            sheet_names: Optional mapping of table_name -> sheet_name
            cache_provider: Optional cache provider
            cache_ttl: Cache TTL in seconds
        """
        try:
            excel_file = pd.ExcelFile(excel_path)
            dataframes = {}
            
            if sheet_names:
                for table_name, sheet_name in sheet_names.items():
                    try:
                        dataframes[table_name] = pd.read_excel(excel_file, sheet_name=sheet_name)
                        logger.info(f"Loaded Excel sheet: {sheet_name} as table: {table_name}")
                    except Exception as e:
                        logger.error(f"Failed to load Excel sheet {sheet_name}: {e}")
            else:
                # Use sheet names as table names
                for sheet_name in excel_file.sheet_names:
                    try:
                        dataframes[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name)
                        logger.info(f"Loaded Excel sheet: {sheet_name}")
                    except Exception as e:
                        logger.error(f"Failed to load Excel sheet {sheet_name}: {e}")
                        
            return PandasEngine(
                data_sources=dataframes,
                cache_provider=cache_provider,
                cache_ttl=cache_ttl
            )
            
        except Exception as e:
            logger.error(f"Failed to load Excel file {excel_path}: {e}")
            return PandasEngine(
                cache_provider=cache_provider,
                cache_ttl=cache_ttl
            )
    
    @staticmethod
    def from_postgres(
        host: str,
        database: str,
        username: str,
        password: str,
        port: int = 5432,
        cache_provider: Optional[Cache] = None,
        cache_ttl: int = 3600
    ) -> PandasEngine:
        """
        Create engine with PostgreSQL connection
        
        Args:
            host: PostgreSQL host
            database: Database name
            username: Username
            password: Password
            port: Port number (default: 5432)
            cache_provider: Optional cache provider
            cache_ttl: Cache TTL in seconds
        """
        if not POSTGRES_AVAILABLE:
            logger.error("PostgreSQL dependencies not available. Install with: pip install sqlalchemy psycopg2-binary")
            return PandasEngine(
                cache_provider=cache_provider,
                cache_ttl=cache_ttl
            )
        
        postgres_config = {
            'host': host,
            'port': str(port),
            'database': database,
            'username': username,
            'password': password
        }
        
        return PandasEngine(
            postgres_config=postgres_config,
            cache_provider=cache_provider,
            cache_ttl=cache_ttl
        )
    
    @staticmethod
    def from_mixed_sources(
        dataframes: Dict[str, pd.DataFrame] = None,
        csv_files: Dict[str, str] = None,
        excel_file: str = None,
        excel_sheet_mapping: Dict[str, str] = None,
        postgres_config: Dict[str, str] = None,
        cache_provider: Optional[Cache] = None,
        cache_ttl: int = 3600
    ) -> PandasEngine:
        """
        Create engine from multiple sources
        
        Args:
            dataframes: Dictionary of DataFrames
            csv_files: Dictionary of CSV file paths
            excel_file: Excel file path
            excel_sheet_mapping: Excel sheet mapping
            postgres_config: PostgreSQL configuration
            cache_provider: Optional cache provider
            cache_ttl: Cache TTL in seconds
        """
        all_dataframes = {}
        
        # Add DataFrames
        if dataframes:
            all_dataframes.update(dataframes)
        
        # Add CSV files
        if csv_files:
            for table_name, csv_path in csv_files.items():
                try:
                    all_dataframes[table_name] = pd.read_csv(csv_path)
                    logger.info(f"Loaded CSV: {csv_path} as {table_name}")
                except Exception as e:
                    logger.error(f"Failed to load CSV {csv_path}: {e}")
        
        # Add Excel files
        if excel_file:
            try:
                excel_data = pd.ExcelFile(excel_file)
                if excel_sheet_mapping:
                    for table_name, sheet_name in excel_sheet_mapping.items():
                        try:
                            all_dataframes[table_name] = pd.read_excel(excel_data, sheet_name=sheet_name)
                            logger.info(f"Loaded Excel sheet: {sheet_name} as {table_name}")
                        except Exception as e:
                            logger.error(f"Failed to load Excel sheet {sheet_name}: {e}")
                else:
                    for sheet_name in excel_data.sheet_names:
                        try:
                            all_dataframes[sheet_name] = pd.read_excel(excel_data, sheet_name=sheet_name)
                            logger.info(f"Loaded Excel sheet: {sheet_name}")
                        except Exception as e:
                            logger.error(f"Failed to load Excel sheet {sheet_name}: {e}")
            except Exception as e:
                logger.error(f"Failed to load Excel file {excel_file}: {e}")
        
        return PandasEngine(
            data_sources=all_dataframes,
            postgres_config=postgres_config,
            cache_provider=cache_provider,
            cache_ttl=cache_ttl
        )

def convert_to_json_serializable(df):
    """
    Convert DataFrame to JSON-serializable format, handling all pandas data types
    """
    try:
        # Create a copy to avoid modifying the original DataFrame
        df_copy = df.copy()
        
        # Convert timedelta and datetime columns to strings
        for column in df_copy.columns:
            try:
                # Use a more robust approach to handle different pandas versions
                dtype = df_copy[column].dtype
                dtype_str = str(dtype).lower()
                
                # Handle different data types based on string representation
                if 'timedelta' in dtype_str:
                    df_copy[column] = df_copy[column].astype(str)  # Convert timedelta to string
                elif 'datetime' in dtype_str:
                    df_copy[column] = df_copy[column].dt.strftime('%Y-%m-%d %H:%M:%S')  # Convert datetime to string
                elif 'categorical' in dtype_str:
                    df_copy[column] = df_copy[column].astype(str)  # Convert categorical to string
                elif 'object' in dtype_str:
                    # Convert object columns to string, handling None/NaN values
                    df_copy[column] = df_copy[column].astype(str).replace('nan', None)
                elif 'period' in dtype_str:
                    df_copy[column] = df_copy[column].astype(str)  # Convert period to string
                elif 'interval' in dtype_str:
                    df_copy[column] = df_copy[column].astype(str)  # Convert interval to string
                elif 'sparse' in dtype_str:
                    df_copy[column] = df_copy[column].astype(str)  # Convert sparse to string
                elif hasattr(dtype, 'kind') and dtype.kind in ['O', 'S', 'U']:
                    # Object, string, or unicode types
                    df_copy[column] = df_copy[column].astype(str).replace('nan', None)
                else:
                    # For any other data type, try to convert to string as fallback
                    df_copy[column] = df_copy[column].astype(str)
            except Exception as e:
                logger.warning(f"Failed to convert column {column} to JSON-serializable format: {e}")
                # Fallback: convert to string
                try:
                    df_copy[column] = df_copy[column].astype(str)
                except Exception as fallback_error:
                    logger.error(f"Even fallback conversion failed for column {column}: {fallback_error}")
                    # Last resort: replace with error message
                    df_copy[column] = f"<conversion_error: {str(fallback_error)}>"

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
        # Fallback: return minimal information
        return {
            "data": [],
            "columns": df.columns.tolist() if hasattr(df, 'columns') else [],
            "row_count": len(df) if hasattr(df, '__len__') else 0,
            "error": f"Failed to serialize data: {str(e)}"
        }