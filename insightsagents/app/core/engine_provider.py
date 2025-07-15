from typing import Dict, Any, Optional
from enum import Enum
import logging
import pandas as pd
from app.core.engine import Engine
from app.core.pandas_engine import PandasEngine
from app.settings import get_settings, EngineType

logger = logging.getLogger(__name__)


    # Add more engine types as needed

class EngineProvider:
    """Provider for different types of database engines"""
    
    @staticmethod
    def get_engine(
        engine_type: Optional[str] = None,
        data_sources: Optional[Dict[str, Any]] = None,
        connection_string: Optional[str] = None,
        postgres_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Engine:
        """
        Get an engine instance based on the specified type and configuration.
        
        Args:
            engine_type: Type of engine to create (defaults to settings)
            data_sources: Data sources for pandas engine
            connection_string: Connection string for database engines
            postgres_config: PostgreSQL specific configuration
            **kwargs: Additional engine-specific arguments
            
        Returns:
            Engine: Configured engine instance
        """
        settings = get_settings()
        engine_type = engine_type or settings.ENGINE_TYPE or EngineType.PANDAS
        
        try:
            if engine_type == EngineType.PANDAS:
                return PandasEngine(
                    engine_type=engine_type,
                    data_sources=data_sources,
                    connection_string=connection_string,
                    postgres_config=postgres_config,
                    **kwargs
                )
            elif engine_type == EngineType.POSTGRES:
                # Use settings if no explicit config provided
                if postgres_config is None:
                    postgres_config = {
                        "host": settings.POSTGRES_HOST,
                        "port": settings.POSTGRES_PORT,
                        "database": settings.POSTGRES_DB,
                        "username": settings.POSTGRES_USER,
                        "password": settings.POSTGRES_PASSWORD
                    }
                
                # Create PandasEngine with PostgreSQL configuration
                return PandasEngine(
                    engine_type=engine_type,
                    postgres_config=postgres_config,
                    **kwargs
                )
            elif engine_type == EngineType.SQLITE:
                # Use settings if no explicit connection string provided
                if connection_string is None:
                    # Default to in-memory database if no connection string provided
                    connection_string = ":memory:"
                
                # Create PandasEngine with SQLite configuration
                return PandasEngine(
                    engine_type=engine_type,
                    connection_string=connection_string,
                    data_sources=data_sources,  # Allow data sources for SQLite
                    **kwargs
                )
            else:
                raise ValueError(f"Unsupported engine type: {engine_type}")
                
        except Exception as e:
            logger.error(f"Error creating engine of type {engine_type}: {str(e)}")
            raise

# Example usage:
def example_engine_usage():
    """Example of how to use the engine provider"""
    # Get engine with default settings (PandasEngine)
    default_engine = EngineProvider.get_engine()
    
    # Get engine with custom data sources
    custom_engine = EngineProvider.get_engine(
        engine_type=EngineType.PANDAS,
        data_sources={
            "employees": pd.DataFrame({
                "id": [1, 2, 3],
                "name": ["John", "Jane", "Bob"]
            })
        }
    )
    
    # Get engine with PostgreSQL configuration from settings
    postgres_engine = EngineProvider.get_engine(
        engine_type=EngineType.POSTGRES
    )
    
    # Get engine with custom PostgreSQL configuration
    custom_postgres_engine = EngineProvider.get_engine(
        engine_type=EngineType.POSTGRES,
        postgres_config={
            "host": "custom-host",
            "port": 5432,
            "database": "custom-db",
            "username": "custom-user",
            "password": "custom-password"
        }
    )
    
    # Get engine with SQLite configuration
    sqlite_engine = EngineProvider.get_engine(
        engine_type=EngineType.SQLITE,
        connection_string="path/to/database.db"
    )
    
    # Get engine with SQLite and data sources
    sqlite_with_data_engine = EngineProvider.get_engine(
        engine_type=EngineType.SQLITE,
        connection_string="path/to/database.db",
        data_sources={
            "employees": pd.DataFrame({
                "id": [1, 2, 3],
                "name": ["John", "Jane", "Bob"]
            })
        }
    ) 