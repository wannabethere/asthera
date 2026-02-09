# Setting Up Contextual Graph PostgreSQL Tables

## Problem
When ingesting contextual edges, you may encounter this error:
```
asyncpg.exceptions.UndefinedTableError: relation "contexts" does not exist
```

This happens because the PostgreSQL tables required for storing contextual graph data haven't been created yet.

## Solution

### Option 1: Create Tables Using Python Script (Recommended)

Run the migration script:

```bash
cd /Users/sameermangalampalli/flowharmonicai/knowledge
python app/indexing/examples/create_contextual_graph_tables.py
```

This will:
- Create the `contexts` table
- Create the `contextual_relationships` table
- Create necessary indexes
- Verify the tables were created

### Option 2: Create Tables Using SQL Script

If you prefer to run SQL directly:

```bash
psql -U your_username -d your_database -f app/indexing/examples/create_contextual_graph_tables.sql
```

Or connect to your database and run:

```sql
-- Create contexts table
CREATE TABLE IF NOT EXISTS contexts (
    context_id SERIAL PRIMARY KEY,
    context_type VARCHAR(100) NOT NULL DEFAULT 'organizational_situational',
    context_name VARCHAR(255) NOT NULL UNIQUE,
    context_definition JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create contextual_relationships table
CREATE TABLE IF NOT EXISTS contextual_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    target_entity_id VARCHAR(255) NOT NULL,
    context_id INTEGER NOT NULL REFERENCES contexts(context_id) ON DELETE CASCADE,
    strength FLOAT DEFAULT 0.0,
    confidence FLOAT DEFAULT 0.0,
    reasoning TEXT,
    valid_from TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_entity_id, relationship_type, target_entity_id, context_id)
);

-- Create indexes (see full SQL file for all indexes)
CREATE INDEX IF NOT EXISTS idx_contexts_context_name ON contexts(context_name);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_source ON contextual_relationships(source_entity_id);
-- ... (see full SQL file for all indexes)
```

## What Gets Created

### 1. `contexts` Table
Stores organizational and situational contexts:
- `context_id` (SERIAL PRIMARY KEY): Auto-incrementing integer ID
- `context_type` (VARCHAR): Type of context (default: 'organizational_situational')
- `context_name` (VARCHAR UNIQUE): Unique name/identifier for the context
- `context_definition` (JSONB): JSON definition of the context
- `created_at`, `updated_at`: Timestamps

### 2. `contextual_relationships` Table
Stores relationships between entities:
- `id` (SERIAL PRIMARY KEY): Auto-incrementing integer ID
- `source_entity_id` (VARCHAR): ID of the source entity
- `relationship_type` (VARCHAR): Type of relationship (e.g., 'HAS_CONTROL', 'MITIGATES_RISK')
- `target_entity_id` (VARCHAR): ID of the target entity
- `context_id` (INTEGER): Foreign key to contexts table
- `strength` (FLOAT): Relationship strength (0.0 to 1.0)
- `confidence` (FLOAT): Relationship confidence (0.0 to 1.0)
- `reasoning` (TEXT): Human-readable description of the relationship
- `valid_from` (TIMESTAMP): When the relationship becomes valid
- `created_at`, `updated_at`: Timestamps
- Unique constraint on (source_entity_id, relationship_type, target_entity_id, context_id)

## After Creating Tables

Once the tables are created, you can safely run the ingestion:

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix comprehensive_index \
    --content-types contextual_edges
```

The ingestion will now:
- ✅ Save edges to ChromaDB vector store
- ✅ Save edges to PostgreSQL `contextual_relationships` table
- ✅ Create contexts in PostgreSQL `contexts` table as needed

## Graceful Handling

The code has been updated to gracefully handle missing tables:
- If tables don't exist, it will log a warning and skip PostgreSQL saves
- Vector store saves will still work
- You'll see a message like: "PostgreSQL table 'contexts' does not exist. Skipping PostgreSQL save."

## Verification

To verify tables were created:

```sql
-- Check if tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('contexts', 'contextual_relationships');

-- Count contexts
SELECT COUNT(*) FROM contexts;

-- Count relationships
SELECT COUNT(*) FROM contextual_relationships;
```

## Troubleshooting

### If you get permission errors:
Make sure your database user has CREATE TABLE permissions:
```sql
GRANT CREATE ON DATABASE your_database TO your_user;
```

### If tables already exist:
The scripts use `CREATE TABLE IF NOT EXISTS`, so it's safe to run multiple times.

### If you want to start fresh:
```sql
DROP TABLE IF EXISTS contextual_relationships CASCADE;
DROP TABLE IF EXISTS contexts CASCADE;
```
Then run the creation script again.
