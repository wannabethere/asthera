# CSV to PostgreSQL Importer

This tool imports CSV files from the `data/cvedata/data` directory into PostgreSQL tables using table names and schema definitions from corresponding JSON metadata files in `data/sql_meta/cve_data`.

## Features

- **Automatic Mapping**: Automatically maps CSV files to PostgreSQL tables using JSON metadata
- **Data Type Inference**: Intelligently infers and converts data types based on metadata and data content
- **Batch Processing**: Efficiently processes large CSV files in batches
- **Error Handling**: Comprehensive error handling and logging
- **Dry Run Mode**: Test the import process without making database changes
- **Flexible Configuration**: JSON-based configuration for easy customization

## Installation

1. Install required Python packages:
```bash
pip install -r requirements_import.txt
```

2. Ensure you have PostgreSQL running and accessible

## Configuration

### Create Configuration File

Run the script with `--create-config` to generate a default configuration file:

```bash
python csv_to_postgres_importer.py --create-config
```

This creates a `config.json` file with default settings:

```json
{
  "csv_directory": "data/cvedata/data",
  "metadata_directory": "data/sql_meta/cve_data",
  "dry_run": false,
  "database": {
    "host": "localhost",
    "port": 5432,
    "database": "cve_data",
    "user": "postgres",
    "password": "password"
  }
}
```

### Customize Configuration

Edit `config.json` to match your environment:

- **csv_directory**: Path to directory containing CSV files
- **metadata_directory**: Path to directory containing JSON metadata files
- **dry_run**: Set to `true` for testing without database operations
- **database**: PostgreSQL connection parameters

## Usage

### Basic Import

```bash
python csv_to_postgres_importer.py
```

### Dry Run (Test Mode)

```bash
python csv_to_postgres_importer.py --dry-run
```

### Custom Configuration

```bash
python csv_to_postgres_importer.py --config my_config.json
```

### Test the Importer

```bash
python test_import.py
```

## How It Works

### 1. File Mapping

The importer automatically maps CSV files to their corresponding metadata files:

- `agents-part-00000-*.csv` → `mdl_agents.json`
- `cve.csv` → `mdl_cve.json`
- `vendors.csv` → `mdl_software.json`
- etc.

### 2. Metadata Processing

For each CSV file, the importer:

1. Loads the corresponding JSON metadata file
2. Extracts the target table name from `models[0].tableReference.table`
3. Gets column definitions and data types
4. Creates the PostgreSQL table if it doesn't exist

### 3. Data Processing

The importer:

1. Reads the CSV file using pandas
2. Cleans the data (removes empty rows, handles nulls)
3. Infers and converts data types based on metadata
4. Inserts data into PostgreSQL using efficient bulk operations

## File Structure

```
├── csv_to_postgres_importer.py  # Main importer script
├── test_import.py               # Test script
├── config.json                  # Configuration file
├── requirements_import.txt      # Python dependencies
├── README_CSV_IMPORT.md         # This file
├── data/
│   ├── cvedata/data/           # CSV files
│   │   ├── agents-part-*.csv
│   │   ├── cve.csv
│   │   ├── vendors.csv
│   │   └── ...
│   └── sql_meta/cve_data/      # JSON metadata files
│       ├── mdl_agents.json
│       ├── mdl_cve.json
│       ├── mdl_software.json
│       └── ...
```

## Example Output

```
2024-01-15 10:30:00 - INFO - Built mapping for 8 CSV files
2024-01-15 10:30:00 - INFO - Database connection established
2024-01-15 10:30:00 - INFO - Processing CSV file: agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv
2024-01-15 10:30:00 - INFO - Loaded metadata from mdl_agents.json
2024-01-15 10:30:00 - INFO - Target table: dev_agents
2024-01-15 10:30:00 - INFO - Read 10000 rows from agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv
2024-01-15 10:30:00 - INFO - Created table dev_agents
2024-01-15 10:30:00 - INFO - Inserted 10000 rows into dev_agents
2024-01-15 10:30:00 - INFO - Successfully imported agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv to dev_agents
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running
   - Verify connection parameters in config.json
   - Ensure database exists

2. **No Metadata File Found**
   - Check file naming patterns
   - Verify metadata files exist in sql_meta/cve_data directory

3. **Data Type Conversion Errors**
   - Check CSV data format
   - Review metadata column definitions
   - Use dry-run mode to test

### Logs

The importer creates detailed logs in:
- Console output (INFO level and above)
- `csv_import.log` file (all levels)

## Advanced Usage

### Programmatic Usage

```python
from csv_to_postgres_importer import CSVToPostgresImporter

# Create configuration
config = {
    "csv_directory": "data/cvedata/data",
    "metadata_directory": "data/sql_meta/cve_data",
    "dry_run": False,
    "database": {
        "host": "localhost",
        "port": 5432,
        "database": "cve_data",
        "user": "postgres",
        "password": "password"
    }
}

# Create and run importer
importer = CSVToPostgresImporter(config)
results = importer.import_all_csv_files()

# Check results
for csv_file, success in results.items():
    print(f"{csv_file}: {'SUCCESS' if success else 'FAILED'}")
```

### Custom Data Processing

You can extend the importer by subclassing `CSVToPostgresImporter` and overriding methods like:
- `_clean_dataframe()`: Custom data cleaning
- `_infer_data_types()`: Custom type inference
- `_insert_data()`: Custom insertion logic

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Run in dry-run mode to test without database changes
3. Use the test script to verify functionality
4. Review the configuration and file mappings
