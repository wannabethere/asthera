# Document Management Database Schema

This directory contains SQL scripts for setting up the document management database schema used by the DocumentIngestionService.

## Overview

The document management system supports:
- **Multi-tenant architecture** with domain-based organization
- **Document versioning** for tracking changes over time
- **Insight extraction** with flexible JSON storage
- **Full-text search** capabilities
- **TF-IDF indexing** for keyword-based retrieval
- **Multiple document types** (PDF, Word, Google Docs, Wiki, etc.)

## Files

### 1. `create_document_tables.sql`
**Purpose**: Creates the complete database schema from scratch
**Use when**: Setting up a new database or starting fresh
**Features**:
- Creates `doc_versions` and `doc_insight_versions` tables
- Sets up comprehensive indexes for performance
- Creates useful views and functions
- Includes sample data and test queries
- Adds constraints and validation rules

### 2. `migrate_document_tables.sql`
**Purpose**: Migrates existing document tables to the new schema
**Use when**: Updating an existing database with document tables
**Features**:
- Backs up existing data before migration
- Adds new columns (domain_id, chunk_content, key_phrases, etc.)
- Migrates data from old structure to new structure
- Creates new indexes and constraints
- Validates data integrity after migration

### 3. `setup_document_tables.sh`
**Purpose**: Automated setup script for easy deployment
**Use when**: You want a simple command to set up the database
**Features**:
- Checks PostgreSQL connection
- Runs appropriate SQL script
- Validates table creation
- Provides helpful error messages and guidance

## Quick Start

### Option 1: Using the Setup Script (Recommended)

```bash
# Navigate to the sql directory
cd dataservices/sql

# Set your database credentials (optional)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=genieml
export DB_USER=postgres
export DB_PASSWORD=your_password

# Run the setup script
./setup_document_tables.sh

# Or for existing databases, run migration
./setup_document_tables.sh --migrate
```

### Option 2: Manual SQL Execution

```bash
# For new databases
psql -h localhost -U postgres -d genieml -f create_document_tables.sql

# For existing databases
psql -h localhost -U postgres -d genieml -f migrate_document_tables.sql
```

## Database Schema

### Tables

#### `doc_versions`
Stores document content and metadata with versioning support.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `document_id` | UUID | Document identifier |
| `source_type` | TEXT | Source of the document (file_upload, api, etc.) |
| `document_type` | TEXT | Type of document (financial_report, etc.) |
| `version` | INTEGER | Version number |
| `content` | TEXT | Document content |
| `json_metadata` | JSONB | Additional metadata |
| `created_at` | TIMESTAMP | Creation timestamp |
| `created_by` | TEXT | User who created the document |
| `domain_id` | TEXT | Domain for multi-tenant support |

#### `doc_insight_versions`
Stores extracted insights and analysis results.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `insight_id` | UUID | Insight identifier |
| `document_id` | UUID | Reference to document |
| `version` | INTEGER | Version number |
| `source_type` | TEXT | Source of the document |
| `document_type` | TEXT | Type of document |
| `event_timestamp` | TIMESTAMP | When the insight was created |
| `chromadb_ids` | TEXT[] | ChromaDB vector IDs |
| `event_type` | TEXT | Type of processing event |
| `created_at` | TIMESTAMP | Creation timestamp |
| `created_by` | TEXT | User who created the insight |
| `domain_id` | TEXT | Domain for multi-tenant support |
| `chunk_content` | TEXT | Consolidated chunk content |
| `key_phrases` | TEXT[] | Extracted key phrases |
| `insights` | JSONB | Flexible insights data |
| `extraction_config` | JSONB | Extraction configuration |
| `extraction_date` | TIMESTAMP | When extraction was performed |

### Views

#### `latest_document_versions`
Shows the latest version of each document.

#### `latest_insight_versions`
Shows the latest version of each insight.

#### `documents_with_insights`
Joins documents with their latest insights for easy querying.

### Functions

#### `get_document_by_id(doc_id UUID)`
Retrieves a document by its ID with the latest version.

#### `get_insights_by_document_id(doc_id UUID)`
Retrieves all insights for a specific document.

#### `search_documents_by_content(search_query TEXT, domain_filter TEXT, doc_type_filter TEXT, limit_count INTEGER)`
Searches documents by content using full-text search.

#### `search_insights_by_phrases(phrase_array TEXT[], domain_filter TEXT, doc_type_filter TEXT, limit_count INTEGER)`
Searches insights by key phrases.

## Performance Optimization

The schema includes comprehensive indexing for optimal performance:

### Full-Text Search Indexes
- `idx_doc_versions_content_fts`: Full-text search on document content
- `idx_doc_insight_versions_chunk_content_fts`: Full-text search on chunk content

### GIN Indexes for JSONB and Arrays
- `idx_doc_versions_json_metadata`: JSON metadata queries
- `idx_doc_insight_versions_insights`: Insights JSON queries
- `idx_doc_insight_versions_key_phrases`: Key phrases array queries
- `idx_doc_insight_versions_chromadb_ids`: ChromaDB IDs array queries

### Composite Indexes
- `idx_doc_insight_versions_domain_doc_type`: Domain + document type queries
- `idx_doc_insight_versions_domain_source_type`: Domain + source type queries

## Example Queries

### Basic Queries

```sql
-- Get all documents in a domain
SELECT * FROM latest_document_versions WHERE domain_id = 'domain_123';

-- Get documents with their insights
SELECT * FROM documents_with_insights WHERE domain_id = 'domain_123';

-- Search documents by content
SELECT * FROM search_documents_by_content('revenue growth', 'domain_123', 'financial_report', 5);

-- Search insights by key phrases
SELECT * FROM search_insights_by_phrases(ARRAY['revenue', 'KPI'], 'domain_123', 'financial_report', 5);
```

### Advanced Queries

```sql
-- Find insights containing specific business intelligence
SELECT * FROM doc_insight_versions 
WHERE insights ? 'business_intelligence' 
AND domain_id = 'domain_123';

-- Get insights by extraction date range
SELECT * FROM doc_insight_versions 
WHERE extraction_date BETWEEN '2024-01-01' AND '2024-12-31'
AND domain_id = 'domain_123';

-- Find documents with specific key phrases
SELECT * FROM doc_insight_versions 
WHERE key_phrases && ARRAY['financial', 'metrics']
AND domain_id = 'domain_123';
```

### Performance Monitoring

```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE tablename IN ('doc_versions', 'doc_insight_versions');

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes 
WHERE tablename IN ('doc_versions', 'doc_insight_versions')
ORDER BY idx_scan DESC;
```

## Integration with DocumentIngestionService

The database schema is designed to work seamlessly with the DocumentIngestionService:

1. **Session Manager Integration**: Uses the same session management pattern as other services
2. **Domain Support**: Full multi-tenant support with domain-based organization
3. **Async Operations**: All database operations are async for high performance
4. **Flexible Storage**: JSONB columns allow for flexible insight storage
5. **Search Integration**: Full-text search and TF-IDF indexing support

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure the database user has CREATE, INSERT, UPDATE, DELETE permissions
2. **Extension Missing**: Make sure `uuid-ossp` and `pg_trgm` extensions are available
3. **Migration Issues**: Check the backup tables if migration fails
4. **Performance Issues**: Monitor index usage and consider additional indexes

### Getting Help

1. Check the PostgreSQL logs for detailed error messages
2. Verify your connection parameters
3. Ensure all required extensions are installed
4. Check the backup tables if migration was attempted

## Maintenance

### Regular Tasks

1. **Monitor Performance**: Check index usage and query performance
2. **Cleanup Old Data**: Consider archiving old document versions
3. **Update Statistics**: Run `ANALYZE` on tables regularly
4. **Backup Data**: Regular backups of the database

### Monitoring Queries

```sql
-- Check for missing domain_id values
SELECT COUNT(*) FROM doc_versions WHERE domain_id IS NULL;
SELECT COUNT(*) FROM doc_insight_versions WHERE domain_id IS NULL;

-- Check data distribution
SELECT domain_id, COUNT(*) FROM doc_versions GROUP BY domain_id;
SELECT document_type, COUNT(*) FROM doc_insight_versions GROUP BY document_type;
```

## Security Considerations

1. **Domain Isolation**: Always filter by domain_id in queries
2. **User Permissions**: Use appropriate database user permissions
3. **Data Encryption**: Consider encrypting sensitive document content
4. **Access Logging**: Monitor database access and queries
5. **Backup Security**: Secure your database backups

## Version History

- **v1.0**: Initial schema with basic document and insight tables
- **v2.0**: Added domain support and simplified structure
- **v2.1**: Added comprehensive indexing and performance optimization
- **v2.2**: Added views, functions, and migration support
