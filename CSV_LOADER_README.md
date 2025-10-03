# CSV to PostgreSQL Data Loader

This script loads CSV files into PostgreSQL tables based on MDL (Model Definition Language) JSON configurations. It automatically maps CSV files to their corresponding database tables and handles table creation, data loading, and optional table dropping.

## Features

- **Automatic Table Mapping**: Maps CSV files to PostgreSQL tables based on MDL JSON schemas
- **Flexible Data Loading**: Supports both drop-and-reload and append-only modes
- **Schema Generation**: Automatically creates PostgreSQL tables from MDL schemas
- **Error Handling**: Comprehensive logging and error handling
- **Configuration Management**: JSON-based configuration for database and file paths

## Table Mappings

The script automatically maps the following CSV files to PostgreSQL tables:

| Table Name | CSV File | MDL Schema | Description |
|------------|----------|------------|-------------|
| `dev_agents` | `agents-part-00000-*.csv` | `mdl_agents.json` | Security monitoring agents |
| `dev_cve` | `cve.csv` | `mdl_cve.json` | CVE vulnerability data |
| `dev_assets` | `assets-part-00000-*.csv` | `mdl_assets.json` | IT asset inventory |
| `dev_software_instances` | `software_instances-part-00000-*.csv` | `mdl_software_instances.json` | Software inventory |
| `dev_vuln_instance` | `vuln_instance-part-00000-*.csv` | `mdl_vuln_instance.json` | Vulnerability instances |
| `dev_interfaces` | `interfaces-part-00000-*.csv` | `mdl_interfaces.json` | Network devices |

## Installation

1. Install required dependencies:
```bash
pip install -r requirements_csv_loader.txt
```

2. Ensure PostgreSQL is running and accessible

## Configuration

Create a configuration file (`config.json`) with your database settings:

```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "database": "cve_data",
    "user": "postgres",
    "password": "your_password"
  },
  "data_directory": "/path/to/csv/files",
  "mdl_directory": "/path/to/mdl/schemas"
}
```

You can also create a sample configuration file:
```bash
python csv_to_postgres_loader.py --create-config sample_config.json
```

## Usage

### Basic Usage

Load all tables with drop-and-reload mode:
```bash
python csv_to_postgres_loader.py --config config.json --drop-tables
```

Load all tables in append mode:
```bash
python csv_to_postgres_loader.py --config config.json --append-only
```

### Advanced Usage

Load a specific table:
```bash
python csv_to_postgres_loader.py --config config.json --table dev_agents --drop-tables
```

### Command Line Options

- `--config`: Path to configuration JSON file (required)
- `--drop-tables`: Drop existing tables before loading data
- `--append-only`: Append data to existing tables (don't truncate)
- `--table`: Process only a specific table name
- `--create-config`: Create a sample configuration file and exit

### Operation Modes

1. **Drop Tables Mode** (`--drop-tables`):
   - Drops existing tables if they exist
   - Creates new tables based on MDL schemas
   - Loads all data from CSV files

2. **Append Mode** (`--append-only`):
   - Keeps existing tables
   - Appends new data to existing tables
   - Creates tables if they don't exist

3. **Default Mode** (no flags):
   - Creates tables if they don't exist
   - Replaces data in existing tables (truncates first)

## Data Type Mapping

The script automatically maps MDL data types to PostgreSQL types:

| MDL Type | PostgreSQL Type |
|----------|-----------------|
| VARCHAR | VARCHAR(255) |
| TEXT | TEXT |
| INTEGER | INTEGER |
| FLOAT | REAL |
| DECIMAL | DECIMAL(10,2) |
| BOOLEAN | BOOLEAN |
| DATE | DATE |
| TIMESTAMP | TIMESTAMP |
| JSON | JSONB |

## Error Handling

The script includes comprehensive error handling:

- **Database Connection**: Validates database connectivity
- **File Validation**: Checks for existence of CSV and MDL files
- **Schema Validation**: Validates MDL schema structure
- **Data Loading**: Handles encoding issues and data type mismatches
- **Logging**: Detailed logging to both file and console

## Logging

Logs are written to:
- Console output (INFO level and above)
- `csv_loader.log` file (all levels)

## Example Workflow

1. **First-time setup**:
```bash
# Create configuration
python csv_to_postgres_loader.py --create-config config.json
# Edit config.json with your database settings

# Load all data (drop existing tables)
python csv_to_postgres_loader.py --config config.json --drop-tables
```

2. **Incremental updates**:
```bash
# Append new data to existing tables
python csv_to_postgres_loader.py --config config.json --append-only
```

3. **Update specific table**:
```bash
# Update only the agents table
python csv_to_postgres_loader.py --config config.json --table dev_agents --drop-tables
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**:
   - Check database credentials in config.json
   - Ensure PostgreSQL is running
   - Verify network connectivity

2. **CSV File Not Found**:
   - Check file paths in config.json
   - Ensure CSV files exist in the data directory

3. **MDL Schema Error**:
   - Verify MDL JSON files are valid
   - Check that table names match between CSV and MDL files

4. **Data Type Errors**:
   - Check for encoding issues in CSV files
   - Verify data format matches expected types

### Debug Mode

For detailed debugging, check the log file:
```bash
tail -f csv_loader.log
```

## File Structure

```
project/
├── csv_to_postgres_loader.py    # Main script
├── config.json                  # Configuration file
├── requirements_csv_loader.txt  # Python dependencies
├── CSV_LOADER_README.md         # This documentation
├── csv_loader.log              # Log file (created at runtime)
├── data/
│   └── cvedata/
│       └── data/               # CSV files directory
└── sql_meta/
    └── cve_data/               # MDL schema files directory
```

## Performance Considerations

- Large CSV files are processed in chunks (1000 rows at a time)
- Use `--append-only` for incremental updates to avoid recreating tables
- Consider database indexing for large datasets
- Monitor disk space during large data loads

## Security Notes

- Store database credentials securely
- Use environment variables for production deployments
- Consider using connection pooling for high-volume operations
- Validate input data before loading
