import json
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union, cast, TypeVar
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier, Literal, Composed

from app.config.settings import get_settings

SqlQuery = Union[str, SQL, Composed]

class PostgresDB:
    def __init__(self, connection_params: Dict[str, Any] | None = None) -> None:
        """
        Initialize database connection parameters.

        Args:
            connection_params: Optional dictionary of connection parameters.
            Optionally accepting these so this class can be used without running the api.
            If not provided, the connection parameters will be taken from the environment variables.
        """
        if connection_params is None:
            settings = get_settings()
            self.connection_params = {
                "host": settings.DB_HOST,
                "port": settings.DB_PORT,
                "dbname": settings.DB_NAME,
                "user": settings.DB_USER,
                "password": settings.DB_PASSWORD,
            }
        else:
            self.connection_params = connection_params
        self._connection: Optional[psycopg.Connection] = None

    @contextmanager
    def _get_connection(self):
        """Get a database connection using context manager.

        Yields:
            psycopg.Connection: The database connection.
        """
        try:
            self._connection = psycopg.connect(**self.connection_params)
            yield self._connection
        finally:
            if self._connection:
                self._connection.close()
                self._connection = None

    @contextmanager
    def _get_cursor(self):
        """Get a database cursor using context manager.

        Yields:
            psycopg.Cursor: The database cursor.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def execute_query(
        self, query: Union[str, SQL, Composed], params: Optional[Tuple[Any, ...]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query and return results as a list of dictionaries.

        Args:
            query: The SQL query to execute.
            params: Optional tuple of parameters for the query.

        Returns:
            List[Dict[str, Any]]: List of dictionaries containing query results.
        """
        with self._get_cursor() as cursor:
            # Use execute to run the query with the given parameters
            cursor.execute(query, params)  # type: ignore
            return cursor.fetchall()

    def get_record(self, table_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record from the specified table by document_id.

        Args:
            table_name: The name of the table to query.
            document_id: The unique identifier of the document.

        Returns:
            Optional[Dict[str, Any]]: The record if found, None otherwise.
        """
        try:
            uuid_id = UUID(document_id)
        except ValueError:
            return None

        query = SQL("SELECT * FROM {table} WHERE document_id = %s;").format(
            table=Identifier(table_name)
        )
        results = self.execute_query(query, (uuid_id,))
        if not results:
            return None

        record = results[0]
        record["document_id"] = str(record["document_id"])
        return record

    def get_all_records(self, table_name: str, limit: int = -1) -> List[Dict[str, Any]]:
        """Retrieve all records from the specified table.

        Args:
            table_name: The name of the table to query.
            limit: Maximum number of records to return. -1 for no limit.

        Returns:
            List[Dict[str, Any]]: List of records from the table.
        """
        if limit > 0:
            query = SQL("SELECT * FROM {table} LIMIT %s;").format(
                table=Identifier(table_name)
            )
        else:
            query = SQL("SELECT * FROM {table};").format(
                table=Identifier(table_name)
            )
        results = self.execute_query(query, (limit,) if limit > 0 else None)

        # Convert document_id to string in each record
        for record in results:
            record["document_id"] = str(record["document_id"])
        return results

    def insert_record(self, table_name: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Insert a new record into the specified table.

        Args:
            table_name: The name of the table to insert into.
            metadata: A dictionary of metadata fields and values to insert.

        Returns:
            Optional[str]: The document_id of the inserted record, or None if insertion failed.
        """
        # Process metadata to handle dictionary values
        processed_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, dict):
                # Convert dictionary to JSON string
                processed_metadata[key] = json.dumps(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                # Handle lists of dictionaries
                processed_metadata[key] = json.dumps(value)
            else:
                processed_metadata[key] = value

        columns = SQL(", ").join(Identifier(key) for key in processed_metadata.keys())
        placeholders = SQL(", ").join(Literal("%s") for _ in processed_metadata)
        query = SQL("INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING document_id;").format(
            table=Identifier(table_name),
            columns=columns,
            placeholders=placeholders
        )
        params = tuple(processed_metadata.values())
        result = self.execute_query(query, params)
        return str(result[0]["document_id"]) if result else None

    def update_record(
        self, table_name: str, document_id: str, metadata: Dict[str, Any]
    ) -> None:
        """Update an existing record in the specified table.

        Args:
            table_name: The name of the table to update.
            document_id: The unique identifier of the document.
            metadata: A dictionary of metadata fields and values to update.
        """
        try:
            uuid_id = UUID(document_id)
        except ValueError:
            return

        set_clause = SQL(", ").join(Identifier(key) + SQL(" = %s") for key in metadata.keys())
        query = SQL("UPDATE {table} SET {set_clause} WHERE document_id = %s;").format(
            table=Identifier(table_name),
            set_clause=set_clause
        )
        params = (*metadata.values(), uuid_id)
        self.execute_query(query, params)

    def delete_record(self, table_name: str, document_id: str) -> None:
        """Delete a record from the specified table.

        Args:
            table_name: The name of the table to delete from.
            document_id: The unique identifier of the document.
        """
        query = SQL("DELETE FROM {table} WHERE document_id = %s;").format(
            table=Identifier(table_name)
        )
        params = (document_id,)
        with self._get_cursor() as cursor:
            cursor.execute(query, params)

    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database.
        
        Args:
            table_name: The name of the table to check.
            
        Returns:
            bool: True if the table exists, False otherwise.
        """
        query = SQL("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """)
        results = self.execute_query(query, (table_name,))
        return results[0]['exists'] if results else False
        
    def get_record_by_field(self, table_name: str, field_name: str, field_value: Any) -> Optional[Dict[str, Any]]:
        """Retrieve a record from the specified table by a specific field.
        
        Args:
            table_name: The name of the table to query.
            field_name: The name of the field to query by.
            field_value: The value to match in the field.
            
        Returns:
            Optional[Dict[str, Any]]: The record if found, None otherwise.
        """
        query = SQL("SELECT * FROM {table} WHERE {field} = %s;").format(
            table=Identifier(table_name),
            field=Identifier(field_name)
        )
        results = self.execute_query(query, (field_value,))
        if not results:
            return None
            
        record = results[0]
        # Convert document_id to string if it exists
        if 'document_id' in record and record['document_id'] is not None:
            record['document_id'] = str(record['document_id'])
        return record
