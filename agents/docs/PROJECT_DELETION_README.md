# Project Deletion Functionality

This document describes the new project deletion functionality that allows you to delete a project and all its associated data from the document stores.

## Overview

The project deletion functionality provides a comprehensive way to remove all data associated with a specific project ID from all document stores and collections. This includes:

- Database schemas
- Table descriptions
- Historical questions
- Instructions
- Project metadata
- SQL pairs/examples
- Project-specific collections

## Components Added

### 1. DocumentChromaStore.delete_by_project_id()

**Location**: `agents/app/storage/documents.py`

**Purpose**: Deletes all documents for a specific project ID from a ChromaDB collection.

**Method Signature**:
```python
def delete_by_project_id(self, project_id: str) -> Dict[str, int]:
```

**Parameters**:
- `project_id` (str): The project ID to delete documents for

**Returns**:
- Dictionary containing the number of documents deleted

**Features**:
- Counts documents before deletion
- Handles both regular and TF-IDF collections
- Provides detailed logging
- Returns error information if deletion fails

### 2. ProjectReader.delete_project()

**Location**: `agents/app/indexing/project_reader.py`

**Purpose**: Deletes all data associated with a project from all document stores.

**Method Signature**:
```python
async def delete_project(self, project_id: str) -> Dict[str, Any]:
```

**Parameters**:
- `project_id` (str): The project ID to delete

**Returns**:
- Dictionary containing deletion results for each component

**Features**:
- Iterates through all indexing components
- Uses existing `clean()` methods where available
- Falls back to direct document store deletion
- Handles project-specific collections
- Provides comprehensive error handling and reporting

### 3. IndexingOrchestrator.clean_project()

**Location**: `agents/app/indexing/orchestrator.py`

**Purpose**: Clean all indexes for a project using the orchestrator pattern.

**Method Signature**:
```python
async def clean_project(self, project_key: str) -> Dict[str, Any]:
```

**Parameters**:
- `project_key` (str): The project key/ID to clean

**Returns**:
- Dictionary containing cleanup results for each component

## Usage Examples

### Basic Project Deletion

```python
import asyncio
import chromadb
from app.indexing.project_reader import ProjectReader
from app.settings import get_settings

async def delete_project_example():
    # Initialize ChromaDB client
    settings = get_settings()
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    
    # Initialize ProjectReader
    base_path = Path("/path/to/sql_meta")
    reader = ProjectReader(base_path, persistent_client)
    
    # Delete project
    project_id = "your_project_id"
    result = await reader.delete_project(project_id)
    
    print(f"Deleted {result['total_documents_deleted']} documents")
    print(f"Components processed: {result['components_deleted']}")

# Run the deletion
asyncio.run(delete_project_example())
```

### Using the Orchestrator

```python
from app.indexing.orchestrator import IndexingOrchestrator

async def clean_with_orchestrator():
    orchestrator = IndexingOrchestrator()
    result = await orchestrator.clean_project("your_project_id")
    
    print(f"Cleanup results: {result}")

asyncio.run(clean_with_orchestrator())
```

### Direct Document Store Deletion

```python
from app.storage.documents import DocumentChromaStore

def delete_from_specific_store():
    doc_store = DocumentChromaStore(
        persistent_client=client,
        collection_name="db_schema"
    )
    
    result = doc_store.delete_by_project_id("your_project_id")
    print(f"Deleted {result['documents_deleted']} documents")
```

## Return Value Structure

### ProjectReader.delete_project() Returns:

```python
{
    "project_id": "your_project_id",
    "components_deleted": {
        "db_schema": {"documents_deleted": 5},
        "table_description": "cleaned",
        "historical_question": {"documents_deleted": 3},
        "instructions": "cleaned",
        "project_meta": "cleaned",
        "sql_pairs": {"documents_deleted": 10},
        "project_collection": {"documents_deleted": 2}
    },
    "total_documents_deleted": 20,
    "errors": []
}
```

### DocumentChromaStore.delete_by_project_id() Returns:

```python
{
    "documents_deleted": 5
}
```

Or in case of error:

```python
{
    "documents_deleted": 0,
    "error": "Error message"
}
```

## Error Handling

The deletion functionality includes comprehensive error handling:

1. **Component-level errors**: If one component fails, others continue processing
2. **Collection-level errors**: TF-IDF collection errors are logged but don't stop the process
3. **Detailed error reporting**: All errors are collected and returned in the results
4. **Graceful degradation**: Missing clean methods fall back to direct deletion

## Safety Considerations

⚠️ **WARNING**: Project deletion is irreversible. Once deleted, all project data is permanently removed from the document stores.

### Best Practices:

1. **Backup first**: Always backup your data before performing deletions
2. **Test with non-critical projects**: Test the deletion functionality with test projects first
3. **Verify project ID**: Double-check the project ID before deletion
4. **Review results**: Always review the deletion results to ensure expected behavior

## Testing

### Running the Example

```bash
cd agents/app/examples
python delete_project_example.py
```

### Testing in ProjectReader

Uncomment the test function call in `project_reader.py`:

```python
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    
    # Uncomment to test deletion
    asyncio.run(test_delete_project())
```

## Integration with Existing Code

The deletion functionality integrates seamlessly with existing code:

1. **Uses existing clean() methods**: Leverages the existing clean methods in indexing components
2. **Maintains compatibility**: Doesn't break existing functionality
3. **Follows existing patterns**: Uses the same error handling and logging patterns
4. **Extends existing classes**: Adds methods to existing classes without modification

## Future Enhancements

Potential future enhancements could include:

1. **Soft deletion**: Mark documents as deleted instead of removing them
2. **Batch deletion**: Delete multiple projects at once
3. **Deletion scheduling**: Schedule deletions for later execution
4. **Deletion confirmation**: Add interactive confirmation prompts
5. **Deletion history**: Track deletion history and allow restoration
