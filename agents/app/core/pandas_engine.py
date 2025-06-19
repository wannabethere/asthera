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
from .engine import Engine, clean_generation_result, add_quotes
from app.settings import EngineType
# Optional PostgreSQL imports
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
    import psycopg2
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

os.environ["OPENAI_API_KEY"] = "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"
logger = logging.getLogger("lexy-ai-service")


class PandasEngine(Engine):
    def __init__(
        self, 
        engine_type: EngineType = EngineType.PANDAS,
        data_sources: Dict[str, pd.DataFrame] = None, 
        connection_string: str = None,
        postgres_config: Dict[str, str] = None
    ):
        """
        Initialize PandasEngine
        
        Args:
            data_sources: Dictionary mapping table names to pandas DataFrames
            connection_string: Optional SQLite connection string for persistent storage
            postgres_config: Optional PostgreSQL connection configuration
        """
        self.data_sources = data_sources or {}
        self.connection_string = connection_string
        self.postgres_config = postgres_config
        self._temp_db_path = None
        self._postgres_engine = None
        self.engine_type = engine_type
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Setup PostgreSQL if config provided
        if postgres_config and POSTGRES_AVAILABLE:
            self._setup_postgres_connection()
        
    def add_data_source(self, table_name: str, dataframe: pd.DataFrame):
        """Add a pandas DataFrame as a data source"""
        self.data_sources[table_name] = dataframe
        
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
            return pd.read_sql_query(sql, self._postgres_engine)
        except Exception as e:
            logger.warning(f"PostgreSQL query failed: {e}")
            return None

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
            
            # Extract table name and WHERE clause
            table_name = None
            where_clause = None
            select_columns = []
            
            for token in tokens:
                if isinstance(token, sqlparse.sql.Identifier):
                    table_name = token.get_real_name()
                elif isinstance(token, sqlparse.sql.Where):
                    where_clause = str(token)
                elif isinstance(token, sqlparse.sql.IdentifierList):
                    select_columns = [str(col).strip() for col in token.get_identifiers()]
                elif isinstance(token, sqlparse.sql.Identifier) and token.get_name().upper() != 'FROM':
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
            
            return result_df
            
        except Exception as e:
            logger.warning(f"DataFrame query execution failed: {e}")
            return None

    def _execute_sql_sync(self, sql: str, limit: Optional[int] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Synchronous SQL execution using pandas"""
        try:
            # Parse and validate SQL
            quoted_sql = self._parse_and_validate_sql(sql, limit)
            
            if self.engine_type == EngineType.PANDAS:
                # Try direct DataFrame execution first
                result_df = self._execute_df_query(quoted_sql)
            elif self.engine_type == EngineType.POSTGRES:
                result_df = self._execute_postgres_query(quoted_sql)
            elif self.engine_type == EngineType.SQLITE:
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
            print("result_df in _execute_sql_sync", result_df.count())
            # Apply limit if specified
            limit = 1000
            if limit is not None:
                result_df = result_df.iloc[:limit]
            
            #print("result_df in _execute_sql_sync", result_df.to_dict(orient='records'))
            # Format and return result
            return True, convert_to_json_serializable(result_df)
                
        except Exception as e:
            logger.exception(f"Error executing SQL: {e}")
            return False, {
                "error": str(e),
                "data": [],
                "columns": []
            }
    
    async def execute_sql(
        self,
        sql: str,
        session: aiohttp.ClientSession,
        dry_run: bool = True,
        limit: Optional[int] = None,
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Execute SQL query asynchronously using pandas
        
        Args:
            sql: SQL query to execute
            session: aiohttp ClientSession (not used in pandas engine)
            dry_run: If True, validates SQL without executing
            limit: Optional limit for number of rows returned
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
            
            limit = 1000
            sql = f"{sql} LIMIT {limit}"
            # Execute SQL in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            success, result = await loop.run_in_executor(
                self.executor, 
                self._execute_sql_sync, 
                sql, 
                limit
            )
            
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
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Execute SQL query in batches to handle large result sets efficiently
        
        Args:
            sql: SQL query to execute
            session: aiohttp ClientSession (not used in pandas engine)
            batch_size: Number of rows to fetch in each batch
            batch_num: Specific batch number to retrieve (None for all batches)
            max_batches: Maximum number of batches to process (None for unlimited)
            dry_run: If True, validates SQL without executing
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

            # First, get total count
            count_sql = f"SELECT COUNT(*) as total_count FROM ({sql}) as count_query"
            success, count_result = await self.execute_sql(
                count_sql,
                session,
                dry_run=False,
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
                    **kwargs
                )
                
                if not success:
                    return False, {
                        "error": f"Failed to execute batch {batch_num}",
                        "data": [],
                        "columns": []
                    }
                
                return True, {
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
            
            return True, {
                "data": all_data,
                "columns": columns,
                "row_count": len(all_data),
                "total_count": total_count,
                "batches_processed": num_batches,
                "batch_size": batch_size
            }
            
        except Exception as e:
            logger.exception(f"Error in execute_sql_in_batches: {e}")
            return False, {"error": str(e), "data": [], "columns": []}


class PandasEngineConfig:
    """Configuration helper for PandasEngine"""
    
    @staticmethod
    def from_dataframes(dataframes: Dict[str, pd.DataFrame]) -> PandasEngine:
        """Create engine from dictionary of DataFrames"""
        return PandasEngine(data_sources=dataframes)
    
    @staticmethod
    def from_csv_files(csv_files: Dict[str, str]) -> PandasEngine:
        """Create engine from CSV files"""
        dataframes = {}
        for table_name, csv_path in csv_files.items():
            try:
                dataframes[table_name] = pd.read_csv(csv_path)
                logger.info(f"Loaded CSV file: {csv_path} as table: {table_name}")
            except Exception as e:
                logger.error(f"Failed to load CSV file {csv_path}: {e}")
        return PandasEngine(data_sources=dataframes)
    
    @staticmethod
    def from_excel_file(excel_path: str, sheet_names: Dict[str, str] = None) -> PandasEngine:
        """
        Create engine from Excel file
        
        Args:
            excel_path: Path to Excel file
            sheet_names: Optional mapping of table_name -> sheet_name
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
                        
            return PandasEngine(data_sources=dataframes)
            
        except Exception as e:
            logger.error(f"Failed to load Excel file {excel_path}: {e}")
            return PandasEngine()
    
    @staticmethod
    def from_postgres(
        host: str,
        database: str,
        username: str,
        password: str,
        port: int = 5432
    ) -> PandasEngine:
        """
        Create engine with PostgreSQL connection
        
        Args:
            host: PostgreSQL host
            database: Database name
            username: Username
            password: Password
            port: Port number (default: 5432)
        """
        if not POSTGRES_AVAILABLE:
            logger.error("PostgreSQL dependencies not available. Install with: pip install sqlalchemy psycopg2-binary")
            return PandasEngine()
        
        postgres_config = {
            'host': host,
            'port': str(port),
            'database': database,
            'username': username,
            'password': password
        }
        
        return PandasEngine(postgres_config=postgres_config)
    
    @staticmethod
    def from_mixed_sources(
        dataframes: Dict[str, pd.DataFrame] = None,
        csv_files: Dict[str, str] = None,
        excel_file: str = None,
        excel_sheet_mapping: Dict[str, str] = None,
        postgres_config: Dict[str, str] = None
    ) -> PandasEngine:
        """
        Create engine from multiple sources
        
        Args:
            dataframes: Dictionary of DataFrames
            csv_files: Dictionary of CSV file paths
            excel_file: Excel file path
            excel_sheet_mapping: Excel sheet mapping
            postgres_config: PostgreSQL configuration
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
            postgres_config=postgres_config
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