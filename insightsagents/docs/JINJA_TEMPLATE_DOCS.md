# Jinja-Based Database Template System

A powerful, flexible template system for generating database connection code using Jinja2 templating engine. This system allows you to create reusable, configurable templates for different database types and generate executable Python scripts dynamically.

## 🚀 Features

- **Jinja2-Powered**: Leverage the full power of Jinja2 templating
- **Multiple Database Support**: Built-in templates for Trino, PostgreSQL (easily extensible)
- **Configuration Validation**: Automatic validation of connection parameters
- **Schema Generation**: JSON schema generation for template configurations
- **Template Discovery**: Automatic discovery and registration of templates
- **Export Functionality**: Generate and save executable Python scripts
- **Custom Templates**: Easy creation of custom database templates
- **Backward Compatibility**: Works with existing file-based templates

## 📦 Installation

```bash
pip install jinja2 pandas sqlalchemy psycopg2 trino
```

## 🏗️ Project Structure

```
template_system/
├── base_template.py           # Abstract base class for all templates
├── updated_template_manager.py # Main template manager with Jinja support
├── template_registry.py       # Template registration and examples
├── templates/
│   ├── __init__.py
│   ├── trino_template.py      # Trino database template
│   └── postgresql_template.py # PostgreSQL database template
└── generated_scripts/         # Output directory for generated scripts
```

## 🎯 Quick Start

### Basic Usage

```python
from template_system import template_manager

# List available templates
print("Available templates:", template_manager.list_templates())

# Create a simple query
query = "SELECT * FROM users LIMIT 10"

# PostgreSQL configuration
postgres_config = {
    "host": "localhost",
    "port": 5432,
    "database": "mydb",
    "user": "myuser",
    "password": "mypass"
}

# Generate executable code
code = template_manager.create_executable("postgresql", query, postgres_config)
print(code)
```

### Export to File

```python
from pathlib import Path

# Export generated script to file
output_file = Path("my_database_script.py")
template_manager.export_template(
    "postgresql", 
    output_file, 
    query, 
    postgres_config
)
```

## 📋 Built-in Templates

### Trino Template

**Template Name**: `trino`

**Required Dependencies**:
- `pandas`
- `trino`

**Configuration Parameters**:
```python
trino_config = {
    "host": "trino-server.com",
    "port": 8080,                    # Default: 8080
    "catalog": "data_lake",
    "schema": "analytics",
    "user": "analyst",
    "auth_method": None,             # Optional authentication
    "show_info": True,               # Show DataFrame info
    "debug": False                   # Enable debug output
}
```

**Example Usage**:
```python
query = """
SELECT customer_id, SUM(amount) as total
FROM orders 
WHERE date >= date('2024-01-01')
GROUP BY customer_id
ORDER BY total DESC
LIMIT 100
"""

code = template_manager.create_executable("trino", query, trino_config)
```

### PostgreSQL Template

**Template Name**: `postgresql`

**Required Dependencies**:
- `pandas`
- `sqlalchemy`
- `psycopg2`

**Configuration Parameters**:
```python
postgres_config = {
    "host": "postgres-server.com",
    "port": 5432,                    # Default: 5432
    "database": "mydb",
    "user": "myuser",
    "password": "mypass",
    "ssl_mode": "prefer",            # Optional: disable, allow, prefer, require, verify-ca, verify-full
    "connection_pool": True,         # Enable connection pooling
    "pool_size": 5,                  # Pool size
    "max_overflow": 10,              # Max overflow connections
    "pool_timeout": 30,              # Pool timeout in seconds
    "pool_recycle": 3600,            # Pool recycle time in seconds
    "test_connection": True,         # Test connection after creation
    "show_info": True,               # Show DataFrame info
    "show_dtypes": False,            # Show DataFrame data types
    "show_stats": False,             # Show DataFrame statistics
    "debug": False                   # Enable debug output
}
```

## 🛠️ Advanced Usage

### Template Information

```python
# Get detailed template information
info = template_manager.get_template_info("postgresql")
print(f"Dependencies: {info['dependencies']}")
print(f"Required parameters: {info['connection_parameters']}")
print(f"Configuration schema: {info['config_schema']}")
```

### Configuration Validation

```python
# Get configuration schema
schema = template_manager.get_config_schema("postgresql")
print("Configuration schema:", schema)

# Validate configuration
template = template_manager.get_template("postgresql")
is_valid = template.validate_config(my_config)
print(f"Configuration valid: {is_valid}")
```

### Batch Processing

```python
queries = [
    "SELECT COUNT(*) FROM users",
    "SELECT AVG(order_total) FROM orders", 
    "SELECT MAX(created_at) FROM products"
]

for i, query in enumerate(queries):
    script_file = f"query_{i+1}.py"
    template_manager.export_template("postgresql", script_file, query, config)
    print(f"Generated {script_file}")
```

### Template Statistics

```python
stats = template_manager.get_template_stats()
print(f"Total templates: {stats['total_templates']}")
print(f"Templates by dependency: {stats['templates_by_type']}")
```

## 🔧 Creating Custom Templates

### Step 1: Define Template Class

```python
from base_template import BaseTemplate
from typing import Dict, List, Any

class MySQLTemplate(BaseTemplate):
    @property
    def data_source_name(self) -> str:
        return "mysql"
    
    @property
    def required_dependencies(self) -> List[str]:
        return ["pandas", "sqlalchemy", "pymysql"]
    
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

# MySQL connection
MYSQL_HOST = {{ host | quote_string }}
MYSQL_PORT = {{ port | default_port(3306) }}
MYSQL_DATABASE = {{ database | quote_string }}
MYSQL_USER = {{ user | quote_string }}
MYSQL_PASSWORD = {{ password | quote_string }}

try:
    connection_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    engine = create_engine(connection_string)
    
    query = """{{ query }}"""
    df = pd.read_sql_query(query, engine)
    
    print(f"✅ Retrieved {len(df)} rows")
    print(df.head())

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    if 'engine' in locals():
        engine.dispose()'''
    
    def apply_connection_config(self, code: str, config: Dict[str, Any]) -> str:
        return code
```

### Step 2: Register Template

```python
# Register the custom template
template_manager.register_template("mysql", MySQLTemplate)

# Use the custom template
mysql_config = {
    "host": "mysql-server.com",
    "port": 3306,
    "database": "analytics",
    "user": "analyst", 
    "password": "secret123"
}

code = template_manager.create_executable("mysql", "SELECT COUNT(*) FROM users", mysql_config)
```

## 🎨 Jinja2 Features

### Built-in Filters

- `quote_string`: Properly quote string values
- `default_port`: Use default port if none specified
- `connection_string`: Format connection strings
- `safe_name`: Create safe variable names

### Usage in Templates

```jinja2
# String quoting
HOST = {{ host | quote_string }}

# Default values  
PORT = {{ port | default_port(5432) }}

# Conditional blocks
{% if ssl_mode %}
SSL_MODE = {{ ssl_mode | quote_string }}
{% endif %}

# Loops (if needed)
{% for param in connection_params %}
{{ param.upper() }} = {{ param.value | quote_string }}
{% endfor %}
```

## 📊 Template Schema

Templates automatically generate JSON schemas for their configuration:

```python
schema = template_manager.get_config_schema("postgresql")
# Returns:
{
    "type": "object",
    "properties": {
        "host": {"type": "string", "description": "host for postgresql connection"},
        "port": {"type": "string", "description": "port for postgresql connection"},
        "database": {"type": "string", "description": "database for postgresql connection"},
        "user": {"type": "string", "description": "user for postgresql connection"},
        "password": {"type": "string", "description": "password for postgresql connection"},
        "ssl_mode": {
            "type": "string", 
            "enum": ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        }
    },
    "required": ["host", "port", "database", "user", "password"]
}
```

## 🔍 Error Handling

The system includes comprehensive error handling:

```python
try:
    code = template_manager.create_executable("nonexistent", "SELECT 1", {})
except ValueError as e:
    print(f"Template not found: {e}")

try:
    code = template_manager.create_executable("postgresql", "SELECT 1", {"host": "localhost"})
except ValueError as e:
    print(f"Invalid configuration: {e}")

try:
    template_manager.export_template("postgresql", "/invalid/path/script.py", "SELECT 1", config)
except RuntimeError as e:
    print(f"Export failed: {e}")
```

## 🧪 Testing

```python
# Validate all templates
for template_name in template_manager.list_templates():
    is_valid = template_manager.validate_template(template_name)
    print(f"{template_name}: {'✅ Valid' if is_valid else '❌ Invalid'}")

# Preview templates without executing
preview = template_manager.preview_template("postgresql", "SELECT current_timestamp")
print("Preview:", preview[:200] + "...")
```

## 🎯 Best Practices

1. **Security**: Never hardcode credentials in templates
   ```python
   # Good: Use configuration
   config = {"password": os.getenv("DB_PASSWORD")}
   
   # Bad: Hardcoded in template
   # MYSQL_PASSWORD = "hardcoded_password"
   ```

2. **Error Handling**: Always include comprehensive error handling
   ```jinja2
   try:
       # Database operations
   except Exception as e:
       print(f"❌ Error: {e}")
       {% if debug %}
       import traceback
       traceback.print_exc()
       {% endif %}
   ```

3. **Resource Cleanup**: Always close connections
   ```jinja2
   finally:
       if 'engine' in locals():
           engine.dispose()
   ```

4. **Configuration Validation**: Validate configs before use
   ```python
   if not template.validate_config(config):
       raise ValueError("Invalid configuration")
   ```

## 🤝 Contributing

To add support for a new database:

1. Create a new template class inheriting from `BaseTemplate`
2. Implement all required properties and methods
3. Define the Jinja template content
4. Add comprehensive configuration validation
5. Register the template in `TEMPLATE_REGISTRY`
6. Add tests and documentation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.