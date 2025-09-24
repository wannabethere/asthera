# ML Function Registry Structure

## Overview

All ML function registry components have been moved to the `registry` folder under `mltools` for better organization and modularity.

## New Folder Structure

```
insightsagents/app/tools/mltools/
├── registry/
│   ├── __init__.py                           # Registry module exports
│   ├── function_registry.py                  # Core registry system
│   ├── function_search_interface.py          # High-level search interface
│   ├── function_retrieval_service.py         # Agent-friendly service
│   └── initialize_function_registry.py       # CLI initialization script
├── __init__.py                               # Main mltools exports (updated)
└── ... (other mltools modules)
```

## Import Changes

### Before (Old Structure)
```python
from app.tools.mltools.function_registry import MLFunctionRegistry
from app.tools.mltools.function_search_interface import FunctionSearchInterface
from app.tools.mltools.function_retrieval_service import create_function_retrieval_service
```

### After (New Structure)
```python
# Option 1: Import from registry module
from app.tools.mltools.registry import (
    MLFunctionRegistry,
    FunctionSearchInterface,
    create_function_retrieval_service
)

# Option 2: Import from main mltools module (still works)
from app.tools.mltools import (
    MLFunctionRegistry,
    FunctionSearchInterface,
    create_function_retrieval_service
)
```

## Files Moved

1. **`function_registry.py`** → `registry/function_registry.py`
2. **`function_search_interface.py`** → `registry/function_search_interface.py`
3. **`function_retrieval_service.py`** → `registry/function_retrieval_service.py`
4. **`initialize_function_registry.py`** → `registry/initialize_function_registry.py`

## Updated Files

1. **`registry/__init__.py`** - New file that exports all registry components
2. **`mltools/__init__.py`** - Updated to import from registry module
3. **Test files** - Updated import paths
4. **Example files** - Updated import paths
5. **Documentation** - Updated to reflect new structure

## Command Line Usage

The CLI script path has changed:

### Before
```bash
python -m app.tools.mltools.initialize_function_registry --chroma-path ./chroma_db
```

### After
```bash
python -m app.tools.mltools.registry.initialize_function_registry --chroma-path ./chroma_db
```

## Benefits of New Structure

1. **Better Organization**: All registry-related code is in one place
2. **Modularity**: Registry can be imported as a separate module
3. **Cleaner Imports**: Clear separation between registry and other mltools
4. **Maintainability**: Easier to maintain and extend registry functionality
5. **Backward Compatibility**: Old import paths still work through main mltools module

## Testing

Run the structure test to verify everything is working:

```bash
python insightsagents/tests/mltools/test_registry_structure.py
```

This will test:
- Import functionality from both paths
- Class and function identity
- Basic registry functionality

## Migration Guide

If you have existing code using the registry:

1. **No changes needed** if using `from app.tools.mltools import ...`
2. **Update imports** if using direct module imports:
   ```python
   # Old
   from app.tools.mltools.function_registry import MLFunctionRegistry
   
   # New (recommended)
   from app.tools.mltools.registry import MLFunctionRegistry
   ```

3. **Update CLI commands** if using the initialization script:
   ```bash
   # Old
   python -m app.tools.mltools.initialize_function_registry
   
   # New
   python -m app.tools.mltools.registry.initialize_function_registry
   ```

## Registry Components

### Core Components
- **`MLFunctionRegistry`**: Main registry class for managing function metadata
- **`FunctionMetadata`**: Dataclass for structured function information
- **`initialize_function_registry`**: Function to initialize the registry

### Search Components
- **`FunctionSearchInterface`**: High-level search interface
- **`SearchResult`**: Structured search result dataclass
- **`create_search_interface`**: Factory function for search interface

### Service Components
- **`FunctionRetrievalService`**: Agent-friendly service
- **`create_function_retrieval_service`**: Factory function for service

All components are available through both import paths for maximum compatibility.
