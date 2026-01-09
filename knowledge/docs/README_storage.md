# Storage Layer Architecture

This directory contains the storage abstraction layer for the Knowledge App, providing flexible, configurable storage backends for vector stores, caches, and databases.

## Architecture

The storage layer is designed with abstraction in mind, allowing you to switch between different implementations without changing your application code:

- **Vector Store**: ChromaDB (implemented), Qdrant (placeholder), Pinecone (placeholder)
- **Cache**: In-memory TTLCache (implemented), Redis (implemented)
- **Database**: PostgreSQL (implemented), MySQL (placeholder)

## Configuration

All storage backends are configured via `app/core/settings.py`, similar to `genieml/agents/app/settings.py`.

### Environment Variables

```bash
# Vector Store
VECTOR_STORE_TYPE=chroma  # chroma, qdrant, pinecone
CHROMA_USE_LOCAL=true
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Cache
CACHE_TYPE=memory  # memory, redis
CACHE_TTL=120
CACHE_MAXSIZE=1000000

# Database
DATABASE_TYPE=postgres  # postgres, mysql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knowledge_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

## Usage

### Basic Usage

```python
from app.storage.factory import initialize_storage_clients
from langchain_openai import OpenAIEmbeddings

# Initialize all clients
embeddings = OpenAIEmbeddings()
db_client, vector_store_client, cache_client = await initialize_storage_clients(
    embeddings_model=embeddings
)

# Use the clients
await db_client.execute("SELECT * FROM controls")
await vector_store_client.add_documents("collection", ["doc1", "doc2"])
await cache_client.set("key", "value")
```

### Using Individual Clients

```python
from app.storage.database import get_database_client
from app.storage.vector_store import get_vector_store_client
from app.storage.cache import get_cache_client

# Get clients with default settings
db_client = get_database_client()
await db_client.connect()

vector_store = get_vector_store_client()
await vector_store.initialize()

cache = get_cache_client()
```

### With Storage Services

```python
from app.storage.factory import initialize_storage_clients
from app.services.storage.contextual_graph_service import ContextualGraphStorageService

# Initialize clients
db_client, vector_store_client, cache_client = await initialize_storage_clients()

# Create storage service
storage_service = ContextualGraphStorageService(
    db_client=db_client,
    vector_store_client=vector_store_client,
    cache_client=cache_client
)
```

## Implementation Details

### Database Client

The `DatabaseClient` abstraction provides:
- Connection pooling
- Async operations
- Standard query methods (execute, fetch, fetchrow, fetchval)

**PostgreSQL Implementation:**
- Uses `asyncpg` for async PostgreSQL operations
- Supports connection pooling with configurable min/max sizes
- SSL support

**MySQL Implementation:**
- Placeholder (not yet implemented)

### Vector Store Client

The `VectorStoreClient` abstraction provides:
- Collection management
- Document addition with automatic embedding
- Query with embeddings or text
- Metadata filtering

**ChromaDB Implementation:**
- Supports both local (PersistentClient) and remote (HttpClient) modes
- Automatic embedding generation using OpenAIEmbeddings
- Collection caching

**Qdrant/Pinecone:**
- Placeholders (not yet implemented)

### Cache Client

The `CacheClient` abstraction provides:
- Get/Set/Delete operations
- TTL support
- Existence checking

**In-Memory Implementation:**
- Uses `cachetools.TTLCache`
- Configurable maxsize and TTL
- Fast, but not shared across processes

**Redis Implementation:**
- Uses `redis.asyncio` for async operations
- Shared across processes
- Supports SSL and password authentication

## Migration Guide

### From Direct asyncpg.Pool

**Before:**
```python
import asyncpg
pool = await asyncpg.create_pool(...)
service = ControlStorageService(pool)
```

**After:**
```python
from app.storage.database import get_database_client
db_client = get_database_client()
await db_client.connect()
service = ControlStorageService(db_client)
```

### From Direct chromadb.Client

**Before:**
```python
import chromadb
client = chromadb.PersistentClient(...)
```

**After:**
```python
from app.storage.vector_store import get_vector_store_client
vector_store = get_vector_store_client()
await vector_store.initialize()
# Access underlying client if needed: vector_store.client
```

## Settings Reference

See `app/core/settings.py` for all available configuration options.
