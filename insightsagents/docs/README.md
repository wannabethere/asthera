# Query Executor

A Python-based system that generates executable code from SQL query templates for various databases and data sources. This system is designed to create deployable Python scripts that can be run on remote servers.

## 🚀 **New: Template-Based Architecture**

The system has been completely refactored to use a **template-based architecture** that makes it incredibly easy to add new data sources. Each data source is defined by a template class and template file, allowing for:

- **Easy extensibility** - Add new data sources in minutes
- **Dynamic discovery** - Templates are automatically discovered and loaded
- **Consistent interface** - All templates follow the same pattern
- **Validation** - Built-in configuration validation and schema generation

## Features

- **Template-based code generation** from configurable data source templates
- **Automatic query replacement** - replaces placeholder queries with actual SQL
- **Connection configuration** - supports both inline parameters and JSON configuration files
- **Deployment packages** - generates complete deployment packages with requirements and scripts
- **Command-line interface** - easy-to-use CLI for quick generation
- **Remote deployment ready** - includes deployment scripts for automated server setup
- **Dynamic template discovery** - automatically finds and loads available templates
- **Easy extensibility** - add new data sources with minimal code

## Supported Data Sources

### Currently Available
- **PostgreSQL** - Full PostgreSQL support with SQLAlchemy
- **Trino** - Trino/Presto query execution
- **MySQL** - MySQL database connections (example template)

### Adding New Data Sources
Adding new data sources is now incredibly simple! See [ADDING_NEW_DATASOURCES.md](ADDING_NEW_DATASOURCES.md) for a complete guide.

**Example**: Adding Snowflake support takes just 3 files and about 50 lines of code!

## Quick Start

### 1. Generate a simple executor

```bash
# Generate PostgreSQL executor
python cli.py --query "SELECT * FROM users WHERE active = true" --database postgres

# Generate Trino executor with custom output
python cli.py --query "SELECT * FROM sales" --database trino --output sales_query.py

# Generate MySQL executor (new!)
python cli.py --query "SELECT * FROM customers" --database mysql
```

### 2. Generate with connection parameters

```bash
# PostgreSQL with inline connection parameters
python cli.py \
  --query "SELECT * FROM analytics.users" \
  --database postgres \
  --host localhost --port 5432 --user myuser --password mypass

# Trino with inline connection parameters
python cli.py \
  --query "SELECT * FROM hive.default.sales" \
  --database trino \
  --host trino-server --port 8080 --user data_user --catalog hive --schema default
```

### 3. Generate deployment package

```bash
# Generate complete deployment package
python cli.py \
  --query "SELECT * FROM analytics.users" \
  --database postgres \
  --deploy-package \
  --connection-config example_config.json

# Generate package with custom output directory
python cli.py \
  --query "SELECT * FROM sales" \
  --database trino \
  --deploy-package \
  --output-dir my_deployment
```

## Python API Usage

### Basic Usage

```python
from query_executor import QueryExecutor

# Initialize executor
executor = QueryExecutor()

# List available templates
print(f"Available data sources: {executor.list_available_templates()}")

# Generate executable
output_file = executor.generate_executable_code(
    query="SELECT * FROM users WHERE active = true",
    database_type="postgres"
)
print(f"Generated: {output_file}")
```

### With Connection Configuration

```python
# Connection configuration
config = {
    "host": "prod-db.company.com",
    "port": 5432,
    "database": "analytics",
    "user": "analytics_user",
    "password": "secure_password_123"
}

# Generate with config
output_file = executor.generate_executable_code(
    query="SELECT * FROM analytics.users",
    database_type="postgres",
    connection_config=config
)
```

### Generate Deployment Package

```python
# Generate complete deployment package
package_dir = executor.generate_deployment_package(
    query="SELECT * FROM analytics.users",
    database_type="postgres",
    connection_config=config,
    include_requirements=True
)
print(f"Deployment package: {package_dir}")
```

### Template Information

```python
# Get information about available templates
for template_name in executor.list_available_templates():
    info = executor.get_template_info(template_name)
    print(f"\n{template_name.upper()}:")
    print(f"  Dependencies: {', '.join(info['dependencies'])}")
    print(f"  Connection Parameters: {list(info['connection_parameters'].keys())}")
    
    # Get configuration schema
    schema = executor.get_config_schema(template_name)
    print(f"  Config Schema: {schema}")
```

## Configuration Files

### JSON Configuration Format

```json
{
  "host": "prod-db.company.com",
  "port": 5432,
  "database": "analytics",
  "user": "analytics_user",
  "password": "secure_password_123"
}
```

For Trino:
```json
{
  "host": "trino-cluster.company.com",
  "port": 8080,
  "catalog": "hive",
  "schema": "default",
  "user": "data_engineer"
}
```

## Adding New Data Sources

### Quick Start (3 Steps)

1. **Create Template Class** - Inherit from `BaseTemplate` and implement required methods
2. **Create Template File** - Python file with your executable code template
3. **Register Template** - Add to the template registry

### Example: Adding Snowflake Support

```python
# 1. Create template class
class SnowflakeTemplate(BaseTemplate):
    @property
    def data_source_name(self) -> str:
        return "snowflake"
    
    @property
    def required_dependencies(self) -> list:
        return ["pandas>=1.5.0", "snowflake-connector-python>=3.0.0"]
    
    # ... implement other required methods

# 2. Create template file (snowflake_template.py)
# 3. Register in templates/__init__.py
```

**That's it!** Your new data source is now available in the CLI and Python API.

See [ADDING_NEW_DATASOURCES.md](ADDING_NEW_DATASOURCES.md) for complete examples and best practices.

## Deployment

### Single File Deployment

1. Generate the executor:
   ```bash
   python cli.py --query "YOUR_QUERY" --database postgres
   ```

2. Copy the generated file to your remote server

3. Install dependencies:
   ```bash
   pip install pandas sqlalchemy psycopg2-binary  # for PostgreSQL
   # or
   pip install pandas trino  # for Trino
   ```

4. Run the executor:
   ```bash
   python generated_postgres_executor_abc123.py
   ```

### Package Deployment

1. Generate deployment package:
   ```bash
   python cli.py --query "YOUR_QUERY" --database postgres --deploy-package
   ```

2. Copy the entire package directory to your remote server

3. Run the deployment script:
   ```bash
   cd deployment_package_postgres_abc123
   ./deploy.sh
   ```

4. Execute the generated code:
   ```bash
   python3 main.py
   ```

## File Structure

```
insightsagents/app/executor/
├── base_template.py              # Abstract base class for all templates
├── template_manager.py           # Template discovery and management
├── query_executor.py             # Main executor class (updated)
├── cli.py                        # Command-line interface
├── templates/                    # Template implementations
│   ├── __init__.py              # Template registry
│   ├── postgres_template.py     # PostgreSQL template class
│   ├── trino_template.py        # Trino template class
│   └── mysql_template.py        # MySQL template class (example)
├── postgres_template.py          # Original PostgreSQL template file
├── trino_template.py             # Original Trino template file
├── example_config.json           # Example configuration
├── ADDING_NEW_DATASOURCES.md    # Guide for adding new data sources
└── README.md                     # This file
```

## Generated Output

### Single Executable File
- Python script with your query embedded
- Connection parameters configured (if provided)
- Ready to run on any Python environment with required dependencies

### Deployment Package
```
deployment_package_postgres_abc123/
├── main.py                   # Main executable
├── requirements.txt          # Python dependencies (auto-generated)
├── README.md                 # Usage instructions (auto-generated)
├── deploy.sh                 # Automated deployment script
└── template_info.json        # Template metadata and schema
```

## Security Considerations

- **Passwords**: Never commit passwords to version control
- **Connection strings**: Use environment variables or secure configuration management
- **Network access**: Ensure proper firewall rules for database connections
- **Credentials**: Use least-privilege database users

## Troubleshooting

### Common Issues

1. **Template not found**: Ensure your template class is properly registered in `templates/__init__.py`
2. **Connection errors**: Verify database connection parameters and network access
3. **Missing dependencies**: Install required Python packages using `pip install -r requirements.txt`
4. **Permission denied**: Make deployment script executable with `chmod +x deploy.sh`

### Debug Mode

For debugging template discovery and loading:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

executor = QueryExecutor()
# This will show template discovery and loading details
```

## Contributing

### Adding New Data Sources

1. Follow the template pattern in `ADDING_NEW_DATASOURCES.md`
2. Implement the required methods from `BaseTemplate`
3. Create your template file with the `"DUMMY_QUERY PLACE HOLDER"`
4. Register your template in the registry
5. Test thoroughly with various configurations

### Template Requirements

All templates must implement:
- `data_source_name` property
- `required_dependencies` property  
- `connection_parameters` property
- `query_placeholder` property
- `apply_connection_config()` method

## License

This project is part of the GenieML platform. Please refer to the main project license for usage terms.

## What's New

### v2.0 - Template-Based Architecture
- ✅ **Complete refactor** to template-based system
- ✅ **Dynamic template discovery** - no more hardcoded database types
- ✅ **Easy extensibility** - add new data sources in minutes
- ✅ **Automatic validation** - built-in configuration validation
- ✅ **Schema generation** - automatic JSON schema for configurations
- ✅ **Template metadata** - rich information about each template
- ✅ **MySQL template** - example of adding new data sources
- ✅ **Comprehensive documentation** - complete guide for contributors

The new architecture makes it incredibly easy to add support for any database or data source while maintaining backward compatibility!
