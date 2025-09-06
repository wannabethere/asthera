"""
Trino database template using Jinja2 templating.
"""

from typing import Dict, List, Any
from app.executor.base_template import BaseTemplate


# Built-in Templates
class TrinoTemplate(BaseTemplate):
    """Template for generating Trino database connection code."""
    
    @property
    def data_source_name(self) -> str:
        return "trino"
    
    @property
    def required_dependencies(self) -> List[str]:
        return ["pandas", "trino"]
    
    @property
    def connection_parameters(self) -> List[str]:
        return ["host", "port", "catalog", "schema", "user"]
    
    @property
    def query_placeholder(self) -> str:
        return "SELECT 1"
    
    @property
    def jinja_template_content(self) -> str:
        return '''import pandas as pd
from trino.dbapi import connect  # Assuming 'trino-python-client' is installed

# Trino connection details
TRINO_HOST = {{ host | quote_string }}
TRINO_PORT = {{ port | default_port(8080) }}
TRINO_CATALOG = {{ catalog | quote_string }}
TRINO_SCHEMA = {{ schema | quote_string }}
TRINO_USER = {{ user | quote_string }}  # Or other authentication methods as needed
{% if auth_method %}
TRINO_AUTH = {{ auth_method | quote_string }}
{% endif %}

# Connect to Trino
try:
    conn = connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        catalog=TRINO_CATALOG,
        schema=TRINO_SCHEMA,
        user=TRINO_USER{% if auth_method %},
        auth={{ auth_method }}{% endif %}
    )
    cur = conn.cursor()

    # SQL query to select data from your table
    query = """{{ query }}"""

    # Execute the query
    cur.execute(query)

    # Fetch all results
    rows = cur.fetchall()

    # Get column names for the DataFrame
    column_names = [desc[0] for desc in cur.description]

    # Convert to Pandas DataFrame
    df = pd.DataFrame(rows, columns=column_names)

    # Display the DataFrame (optional)
    print("Query executed successfully!")
    print(f"Retrieved {len(df)} rows and {len(df.columns)} columns")
    print()
    print("First 5 rows:")
    print(df.head())
    
{% if show_info %}
    print()
    print("DataFrame info:")
    print(df.info())
{% endif %}

except Exception as e:
    print(f"An error occurred: {e}")
{% if debug %}
    print(f"Connection details: host={TRINO_HOST}, port={TRINO_PORT}, catalog={TRINO_CATALOG}")
{% endif %}

finally:
    if 'conn' in locals() and conn:
        conn.close()
        print("Connection closed.")'''
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values for Trino."""
        return {
            "host": "localhost",
            "port": 8080,
            "catalog": "your_catalog",
            "schema": "your_schema", 
            "user": "your_user",
            "show_info": True,
            "debug": False
        }
