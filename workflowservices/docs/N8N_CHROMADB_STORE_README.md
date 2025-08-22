# N8n ChromaDB Store Utility

This utility provides functionality to store n8n node components into ChromaDB for efficient searching and retrieval. The utility creates a collection called `n8n_store` by default and provides comprehensive methods for managing n8n component data.

## Features

- **Automatic Collection Management**: Creates and manages ChromaDB collections
- **Smart Node Parsing**: Extracts relevant metadata and searchable content from n8n nodes
- **Flexible Storage**: Supports both individual node storage and batch loading from JSON files
- **Advanced Search**: Semantic search with metadata filtering capabilities
- **Collection Statistics**: Monitor collection size and metadata structure
- **Error Handling**: Robust error handling with detailed logging

## Installation

The utility is part of the workflowservices package and requires the following dependencies:

```bash
pip install chromadb
```

## Configuration

The utility automatically uses the ChromaDB configuration from your settings. You can configure it through:

### Environment Variables

```bash
# N8n Store Settings
export N8N_STORE_COLLECTION_NAME="n8n_store"
export N8N_STORE_USE_LOCAL="true"
export N8N_STORE_LOCAL_PATH="n8n_chromadb_store"
export N8N_STORE_HOST="localhost"
export N8N_STORE_PORT="8000"

# ChromaDB Advanced Settings
export CHROMA_ANONYMIZED_TELEMETRY="false"
export CHROMA_ALLOW_RESET="true"
export CHROMA_ISOLATE_COLLECTIONS="false"
```

### .env File

```env
# N8n Store ChromaDB Settings
N8N_STORE_COLLECTION_NAME=n8n_store
N8N_STORE_USE_LOCAL=true
N8N_STORE_LOCAL_PATH=n8n_chromadb_store
N8N_STORE_HOST=localhost
N8N_STORE_PORT=8000

# ChromaDB Advanced Settings
CHROMA_ANONYMIZED_TELEMETRY=false
CHROMA_ALLOW_RESET=true
CHROMA_ISOLATE_COLLECTIONS=false
```

### N8n Store Specific Settings

```python
# N8n Store ChromaDB Settings
N8N_STORE_COLLECTION_NAME: str = "n8n_store"
N8N_STORE_USE_LOCAL: bool = True
N8N_STORE_LOCAL_PATH: str = "n8n_chromadb_store"
N8N_STORE_HOST: str = "localhost"
N8N_STORE_PORT: int = 8000
```

### ChromaDB Advanced Settings

```python
# ChromaDB Advanced Settings
CHROMA_ANONYMIZED_TELEMETRY: bool = False
CHROMA_ALLOW_RESET: bool = True
CHROMA_ISOLATE_COLLECTIONS: bool = False
```

### Storage Modes

- **Local Mode**: Uses `N8N_STORE_LOCAL_PATH` for local storage (default)
- **Remote Mode**: Uses `N8N_STORE_HOST` and `N8N_STORE_PORT` for remote ChromaDB server

## Usage

### 1. Basic Usage

```python
from app.utils.n8n_chromadb_store import N8nChromaDBStore

# Initialize the store (defaults to 'n8n_store' collection)
store = N8nChromaDBStore()

# Get collection statistics
stats = store.get_collection_stats()
print(f"Total nodes: {stats['total_nodes']}")
print(f"Storage type: {stats['storage_type']}")
print(f"Storage path: {stats['storage_path']}")

# Get detailed storage information
storage_info = store.get_storage_info()
print(f"Local path: {storage_info['absolute_local_path']}")
print(f"Path size: {storage_info['local_path_size']} bytes")
```

### 2. Local Storage Configuration

```python
# Force local storage with custom path
local_store = N8nChromaDBStore(
    use_local=True,
    local_path="my_custom_n8n_store"
)

# Use settings defaults
store = N8nChromaDBStore()  # Uses N8N_STORE_USE_LOCAL and N8N_STORE_LOCAL_PATH from settings
```

### 2. Loading Nodes from JSON File

```python
# Load all nodes from a JSON file
stored_ids = store.store_nodes_from_json("path/to/nodes.json")
print(f"Stored {len(stored_ids)} nodes")
```

### 3. Storing Individual Nodes

```python
# Store a single node
node_data = {
    "name": "HTTP Request",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": {"x": 100, "y": 200},
    "parameters": {"url": "https://api.example.com"},
    "properties": [...]
}

node_id = store.store_node(node_data)
print(f"Stored node with ID: {node_id}")
```

### 4. Searching Nodes

```python
# Basic search
results = store.search_nodes("HTTP request", n_results=10)

# Search with metadata filters
filtered_results = store.search_nodes(
    "email", 
    n_results=5,
    filters={"resource": {"$exists": True}}
)

# Process search results
for result in results:
    metadata = result['metadata']
    print(f"Node: {metadata['node_name']}")
    print(f"Type: {metadata['node_type']}")
    print(f"Similarity: {1 - result['distance']:.4f}")
```

### 5. Retrieving Specific Nodes

```python
# Get a node by its ID
node_data = store.get_node_by_id("node_id_here")
if node_data:
    print(f"Node: {node_data['metadata']['node_name']}")
    print(f"Content: {node_data['document']}")
```

### 6. Collection Management

```python
# Get collection statistics
stats = store.get_collection_stats()

# Clear all data
store.clear_collection()
```

## Command Line Interface

A command-line script is provided for easy usage:

```bash
# Load nodes from default nodes.json file
python scripts/load_n8n_to_chromadb.py

# Load nodes from specific file
python scripts/load_n8n_to_chromadb.py --file /path/to/nodes.json

# Use custom collection name
python scripts/load_n8n_to_chromadb.py --collection my_n8n_nodes

# Force local storage
python scripts/load_n8n_to_chromadb.py --local

# Use custom local storage path
python scripts/load_n8n_to_chromadb.py --local --local-path my_custom_store

# Clear existing collection before loading
python scripts/load_n8n_to_chromadb.py --clear

# Search for specific nodes after loading
python scripts/load_n8n_to_chromadb.py --search "HTTP request"

# Just search without loading
python scripts/load_n8n_to_chromadb.py --search "email" --no-load

# Show collection statistics
python scripts/load_n8n_to_chromadb.py --stats
```

## Data Structure

### Stored Metadata

Each node is stored with the following metadata:

- `node_name`: Name of the node
- `node_type`: Type identifier
- `type_version`: Version number
- `position_x`, `position_y`: Node position
- `parameters_count`: Number of parameters
- `properties_count`: Number of properties
- `has_credentials`: Whether node has credentials
- `has_webhook`: Whether node has webhook
- `resource`: Integration resource (if applicable)
- `operation`: Integration operation (if applicable)
- `authentication`: Authentication method (if applicable)
- `created_at`: Timestamp when stored

### Searchable Content

The utility extracts searchable content from:

- Node name and type
- Description fields
- Property names, types, and descriptions
- Parameter values
- Display options

## Examples

See `examples/n8n_chromadb_example.py` for comprehensive usage examples.

## Error Handling

The utility includes comprehensive error handling:

- **Connection Errors**: Handles ChromaDB connection issues gracefully
- **Data Validation**: Validates node data before storage
- **Duplicate Handling**: Generates unique IDs to prevent conflicts
- **Logging**: Detailed logging for debugging and monitoring

## Performance Considerations

- **Large Files**: The `nodes.json` file (18MB) may take time to process
- **Batch Processing**: Nodes are processed in batches with progress logging
- **Memory Usage**: Large JSON files are processed incrementally
- **Indexing**: ChromaDB automatically indexes content for fast search

## Troubleshooting

### Common Issues

1. **Collection Not Found**: Ensure ChromaDB is running and accessible
2. **Permission Errors**: Check ChromaDB connection settings
3. **Memory Issues**: For very large files, consider processing in smaller chunks
4. **Search Results**: Verify the collection contains data before searching

### Debug Mode

Enable verbose logging for debugging:

```bash
python scripts/load_n8n_to_chromadb.py --verbose
```

## API Reference

### N8nChromaDBStore Class

#### Methods

- `__init__(collection_name: str = "n8n_store")`: Initialize the store
- `store_node(node_data: Dict[str, Any]) -> str`: Store a single node
- `store_nodes_from_json(json_file_path: str) -> List[str]`: Load nodes from JSON file
- `search_nodes(query: str, n_results: int = 10, filters: Optional[Dict] = None) -> List[Dict]`: Search nodes
- `get_node_by_id(node_id: str) -> Optional[Dict]`: Retrieve node by ID
- `get_collection_stats() -> Dict[str, Any]`: Get collection statistics
- `clear_collection()`: Clear all data from collection

## Contributing

When contributing to this utility:

1. Follow the existing code style
2. Add comprehensive error handling
3. Include logging for debugging
4. Update this documentation
5. Add tests for new functionality

## License

This utility is part of the workflowservices package and follows the same licensing terms.
