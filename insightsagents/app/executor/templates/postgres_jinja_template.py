"""
PostgreSQL database template using Jinja2 templating.
"""

from typing import Dict, List, Any
from app.executor.base_template import BaseTemplate

class PostgreSQLTemplate(BaseTemplate):
    """Template for generating PostgreSQL database connection code."""
    
    @property
    def data_source_name(self) -> str:
        return "postgresql"
    
    @property
    def required_dependencies(self) -> List[str]:
        return ["pandas", "sqlalchemy", "psycopg2"]
    
    @property
    def connection_parameters(self) -> List[str]:
        return ["host", "port", "database", "user", "password"]
    
    @property
    def query_placeholder(self) -> str:
        return "SELECT 1"
    
    @property
    def jinja_template_content(self) -> str:
        return '''import pandas as pd
from sqlalchemy import create_engine

# --- Step 1: Configure your PostgreSQL connection ---
# It's recommended to use environment variables or secure vaults for sensitive information like passwords.
# Replace the placeholder values with your actual PostgreSQL connection information.
POSTGRES_HOST = {{ host | quote_string }}
POSTGRES_PORT = {{ port | default_port(5432) }}
POSTGRES_DBNAME = {{ database | quote_string }}
POSTGRES_USER = {{ user | quote_string }}
POSTGRES_PASSWORD = {{ password | quote_string }}  # Use secure methods in production
{% if ssl_mode %}
POSTGRES_SSL_MODE = {{ ssl_mode | quote_string }}
{% endif %}

# --- Step 2: Create a SQLAlchemy engine for PostgreSQL ---
# The URL format for PostgreSQL using psycopg2 is:
# postgresql+psycopg2://user:password@host:port/database
try:
{% if ssl_mode %}
    connection_string = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}"
        f"?sslmode={POSTGRES_SSL_MODE}"
    )
{% else %}
    connection_string = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}"
    )
{% endif %}
    
{% if connection_pool %}
    # Create engine with connection pooling
    engine = create_engine(
        connection_string,
        pool_size={{ pool_size | default(5) }},
        max_overflow={{ max_overflow | default(10) }},
        pool_timeout={{ pool_timeout | default(30) }},
        pool_recycle={{ pool_recycle | default(3600) }}
    )
{% else %}
    engine = create_engine(connection_string)
{% endif %}
    
    print("✅ Successfully created PostgreSQL connection engine.")
    
{% if test_connection %}
    # Test the connection
    with engine.connect() as conn:
        result = conn.execute("SELECT version()")
        version = result.fetchone()[0]
        print(f"📊 Connected to: {version}")
{% endif %}

except Exception as e:
    print(f"❌ Error creating PostgreSQL connection engine: {e}")
{% if debug %}
    print(f"Connection string template: postgresql+psycopg2://{POSTGRES_USER}:***@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}")
{% endif %}
    raise

# --- Step 3: Define your SQL query and read into a pandas DataFrame ---
query = """{{ query }}"""

try:
    # Use pandas.read_sql_query() to execute the query and return a DataFrame.
    # The `engine` object handles the connection to PostgreSQL.
    pandas_df = pd.read_sql_query(query, engine)
    
    print()
    print("✅ Successfully fetched data and created a pandas DataFrame.")
    print(f"📊 Retrieved {len(pandas_df)} rows and {len(pandas_df.columns)} columns")
    print()
    print("📋 First 5 rows of the DataFrame:")
    print(pandas_df.head())
    
{% if show_info %}
    print()
    print("📊 DataFrame info:")
    print(pandas_df.info())
{% endif %}
    
{% if show_dtypes %}
    print()
    print("📊 DataFrame data types:")
    print(pandas_df.dtypes)
{% endif %}
    
{% if show_stats %}
    print()
    print("📊 DataFrame statistics:")
    print(pandas_df.describe())
{% endif %}

except Exception as e:
    print(f"❌ Error executing query or creating DataFrame: {e}")
{% if debug %}
    print(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")
{% endif %}
    raise

finally:
    # Always dispose of the engine to close the database connection pool.
    if 'engine' in locals():
        engine.dispose()
        print("🔒 Connection pool closed.")'''
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values for PostgreSQL."""
        return {
            "host": "localhost",
            "port": 5432,
            "database": "your_database",
            "user": "your_user", 
            "password": "your_password",
            "ssl_mode": None,
            "connection_pool": True,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "test_connection": True,
            "show_info": True,
            "show_dtypes": False,
            "show_stats": False,
            "debug": False
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate PostgreSQL-specific configuration."""
        if not super().validate_config(config):
            return False
        
        # Additional PostgreSQL-specific validations
        if config.get("port") and not isinstance(config["port"], int):
            try:
                config["port"] = int(config["port"])
            except ValueError:
                return False
        
        return True