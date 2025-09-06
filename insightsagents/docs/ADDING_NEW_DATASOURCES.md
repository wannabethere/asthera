# Adding New Data Sources

This guide explains how to add new data sources to the QueryExecutor system. The system is designed to be easily extensible, allowing you to add support for any database or data source with minimal effort.

## Overview

The system uses a template-based architecture where each data source is defined by:
1. **Template Class** - Python class that inherits from `BaseTemplate`
2. **Template File** - Python file with the actual executable code template
3. **Configuration** - Connection parameters and dependencies

## Step-by-Step Guide

### Step 1: Create the Template Class

Create a new file in `insightsagents/app/executor/templates/` with your template class:

```python
# insightsagents/app/executor/templates/your_datasource_template.py

from typing import Dict, Any
from pathlib import Path
from ..base_template import BaseTemplate


class YourDataSourceTemplate(BaseTemplate):
    """Your data source template implementation."""
    
    @property
    def data_source_name(self) -> str:
        return "your_datasource"  # This will be the identifier used in commands
    
    @property
    def required_dependencies(self) -> list:
        return [
            "pandas>=1.5.0",
            "your_package>=1.0.0"  # Add your specific dependencies
        ]
    
    @property
    def connection_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "host": {
                "default": "your_default_host",
                "type": "string",
                "required": True,
                "description": "Host description"
            },
            "port": {
                "default": 1234,
                "type": "integer",
                "required": False,
                "description": "Port description"
            },
            # Add more parameters as needed
        }
    
    @property
    def query_placeholder(self) -> str:
        return 'query = "DUMMY_QUERY PLACE HOLDER"'
    
    def apply_connection_config(self, content: str, config: Dict[str, Any]) -> str:
        """Apply connection configuration to the template content."""
        # Replace placeholders in your template
        if "host" in config:
            content = content.replace(
                'YOUR_HOST = "your_default_host"',
                f'YOUR_HOST = "{config["host"]}"'
            )
        
        # Add more replacements as needed
        return content
```

### Step 2: Create the Template File

Create the actual template file that will be used to generate executable code:

```python
# insightsagents/app/executor/your_datasource_template.py

import pandas as pd
# Import your specific packages

# --- Step 1: Configure your connection ---
YOUR_HOST = "your_default_host"
YOUR_PORT = 1234
# Add more configuration variables

# --- Step 2: Create connection ---
try:
    # Your connection logic here
    connection = create_your_connection(YOUR_HOST, YOUR_PORT)
    print("Successfully connected to your data source.")
except Exception as e:
    print(f"Error connecting: {e}")

# --- Step 3: Define your SQL query and execute ---
query = "DUMMY_QUERY PLACE HOLDER"

try:
    # Your query execution logic here
    result = execute_query(connection, query)
    df = pd.DataFrame(result)
    
    print("\nSuccessfully executed query and created DataFrame.")
    print("\nDisplaying the first 5 rows:")
    print(df.head())
    
    print("\nDataFrame info:")
    print(df.info())

except Exception as e:
    print(f"Error executing query: {e}")
finally:
    # Clean up connection
    if 'connection' in locals():
        connection.close()
```

### Step 3: Register the Template

Update `insightsagents/app/executor/templates/__init__.py`:

```python
from .your_datasource_template import YourDataSourceTemplate

# Add to the registry
TEMPLATE_REGISTRY = {
    "postgres": PostgresTemplate,
    "trino": TrinoTemplate,
    "mysql": MySQLTemplate,
    "your_datasource": YourDataSourceTemplate  # Add this line
}

__all__ = [
    "PostgresTemplate", 
    "TrinoTemplate", 
    "MySQLTemplate", 
    "YourDataSourceTemplate",  # Add this line
    "TEMPLATE_REGISTRY"
]
```

### Step 4: Test Your Template

Test that your template works correctly:

```python
from insightsagents.app.executor import QueryExecutor

executor = QueryExecutor()

# List available templates
print(executor.list_available_templates())  # Should include "your_datasource"

# Test template info
info = executor.get_template_info("your_datasource")
print(info)

# Generate executable
output_file = executor.generate_executable_code(
    query="SELECT * FROM your_table",
    database_type="your_datasource"
)
print(f"Generated: {output_file}")
```

## Template Class Requirements

Your template class **MUST** implement these methods and properties:

### Required Properties

- **`data_source_name`** - String identifier for your data source
- **`required_dependencies`** - List of Python package requirements
- **`connection_parameters`** - Dictionary defining connection parameters
- **`query_placeholder`** - String that gets replaced with actual queries

### Required Methods

- **`apply_connection_config(content, config)`** - Apply configuration to template

### Optional Methods

- **`validate_config(config)`** - Custom validation logic (inherited from BaseTemplate)
- **`get_default_config()`** - Default configuration values (inherited from BaseTemplate)
- **`get_config_schema()`** - JSON schema for configuration (inherited from BaseTemplate)

## Connection Parameters Structure

Each connection parameter should have this structure:

```python
"parameter_name": {
    "default": "default_value",      # Default value
    "type": "string",               # Data type (string, integer, boolean)
    "required": True,               # Whether parameter is required
    "description": "Description"    # Human-readable description
}
```

## Example: Adding Snowflake Support

Here's a complete example of adding Snowflake support:

### 1. Template Class

```python
# insightsagents/app/executor/templates/snowflake_template.py

from typing import Dict, Any
from pathlib import Path
from ..base_template import BaseTemplate


class SnowflakeTemplate(BaseTemplate):
    """Snowflake database template implementation."""
    
    @property
    def data_source_name(self) -> str:
        return "snowflake"
    
    @property
    def required_dependencies(self) -> list:
        return [
            "pandas>=1.5.0",
            "snowflake-connector-python>=3.0.0"
        ]
    
    @property
    def connection_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "account": {
                "default": "your_account.snowflakecomputing.com",
                "type": "string",
                "required": True,
                "description": "Snowflake account identifier"
            },
            "user": {
                "default": "your_username",
                "type": "string",
                "required": True,
                "description": "Snowflake username"
            },
            "password": {
                "default": "your_password",
                "type": "string",
                "required": True,
                "description": "Snowflake password"
            },
            "warehouse": {
                "default": "your_warehouse",
                "type": "string",
                "required": True,
                "description": "Snowflake warehouse name"
            },
            "database": {
                "default": "your_database",
                "type": "string",
                "required": True,
                "description": "Snowflake database name"
            },
            "schema": {
                "default": "your_schema",
                "type": "string",
                "required": False,
                "description": "Snowflake schema name"
            }
        }
    
    @property
    def query_placeholder(self) -> str:
        return 'query = "DUMMY_QUERY PLACE HOLDER"'
    
    def apply_connection_config(self, content: str, config: Dict[str, Any]) -> str:
        """Apply Snowflake connection configuration."""
        replacements = {
            "account": ('SNOWFLAKE_ACCOUNT = "your_account.snowflakecomputing.com"', 
                       f'SNOWFLAKE_ACCOUNT = "{config["account"]}"'),
            "user": ('SNOWFLAKE_USER = "your_username"', 
                     f'SNOWFLAKE_USER = "{config["user"]}"'),
            "password": ('SNOWFLAKE_PASSWORD = "your_password"', 
                        f'SNOWFLAKE_PASSWORD = "{config["password"]}"'),
            "warehouse": ('SNOWFLAKE_WAREHOUSE = "your_warehouse"', 
                         f'SNOWFLAKE_WAREHOUSE = "{config["warehouse"]}"'),
            "database": ('SNOWFLAKE_DATABASE = "your_database"', 
                        f'SNOWFLAKE_DATABASE = "{config["database"]}"'),
            "schema": ('SNOWFLAKE_SCHEMA = "your_schema"', 
                      f'SNOWFLAKE_SCHEMA = "{config["schema"]}"')
        }
        
        for param, (old, new) in replacements.items():
            if param in config:
                content = content.replace(old, new)
        
        return content
```

### 2. Template File

```python
# insightsagents/app/executor/snowflake_template.py

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

# --- Step 1: Configure your Snowflake connection ---
SNOWFLAKE_ACCOUNT = "your_account.snowflakecomputing.com"
SNOWFLAKE_USER = "your_username"
SNOWFLAKE_PASSWORD = "your_password"
SNOWFLAKE_WAREHOUSE = "your_warehouse"
SNOWFLAKE_DATABASE = "your_database"
SNOWFLAKE_SCHEMA = "your_schema"

# --- Step 2: Create Snowflake connection ---
try:
    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA
    )
    print("Successfully connected to Snowflake.")
except Exception as e:
    print(f"Error connecting to Snowflake: {e}")

# --- Step 3: Define your SQL query and execute ---
query = "DUMMY_QUERY PLACE HOLDER"

try:
    # Execute query and get results
    cursor = conn.cursor()
    cursor.execute(query)
    
    # Fetch results
    results = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(results, columns=column_names)
    
    print("\nSuccessfully executed query and created DataFrame.")
    print("\nDisplaying the first 5 rows:")
    print(df.head())
    
    print("\nDataFrame info:")
    print(df.info())

except Exception as e:
    print(f"Error executing query: {e}")
finally:
    # Clean up
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals():
        conn.close()
```

### 3. Register Template

```python
# insightsagents/app/executor/templates/__init__.py

from .snowflake_template import SnowflakeTemplate

TEMPLATE_REGISTRY = {
    "postgres": PostgresTemplate,
    "trino": TrinoTemplate,
    "mysql": MySQLTemplate,
    "snowflake": SnowflakeTemplate
}
```

## Best Practices

1. **Follow Naming Conventions**: Use lowercase with underscores for template names
2. **Validate Inputs**: Always validate connection parameters
3. **Handle Errors Gracefully**: Include proper error handling in your templates
4. **Document Parameters**: Provide clear descriptions for all connection parameters
5. **Test Thoroughly**: Test your template with various configurations
6. **Keep Dependencies Minimal**: Only include necessary dependencies

## Troubleshooting

### Common Issues

1. **Template Not Found**: Ensure your template class is properly registered
2. **Import Errors**: Check that all dependencies are available
3. **Configuration Validation**: Verify your connection parameters structure
4. **File Paths**: Ensure template files are in the correct locations

### Debug Mode

Enable debug mode to see what's happening:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

executor = QueryExecutor()
# This will show template discovery and loading details
```

## Next Steps

After adding your data source:

1. **Update Documentation**: Add your data source to the main README
2. **Add Examples**: Create example configurations and usage patterns
3. **Add Tests**: Create test cases for your template
4. **Share**: Consider contributing your template to the community

## Support

If you encounter issues while adding a new data source:

1. Check the existing templates for reference
2. Verify your template class implements all required methods
3. Ensure your template file follows the expected format
4. Test with simple queries first before complex ones

The template system is designed to be flexible and extensible. With proper implementation, you can add support for virtually any data source or database system!
