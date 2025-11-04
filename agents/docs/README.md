# Unified ChromaDB Storage System (Indexing2)

## 🎯 Overview

The Unified ChromaDB Storage System eliminates duplication between `TABLE` and `TABLE_SCHEMA` document types while providing enhanced search capabilities with TF-IDF generation and quick reference lookups.

## 🏗️ Architecture

### Core Components

1. **UnifiedStorage** - Main storage mechanism with TABLE_SCHEMA as primary document
2. **TFIDFGenerator** - TF-IDF vector generation for quick reference lookups
3. **DocumentBuilder** - Enhanced document creation with business context
4. **StorageManager** - High-level orchestration of all components
5. **DDLChunker** - Creates separate TABLE_DOCUMENTs for natural language search
6. **NaturalLanguageSearch** - Natural language search capabilities
7. **QueryBuilder** - Field type-aware query building with dimension vs fact classification
8. **LLMFieldClassifier** - LLM-powered field type classification and intelligent suggestions
9. **LLMQueryOptimizer** - LLM-powered query optimization and performance analysis

### Document Structure

```
TABLE_SCHEMA (Primary Document)
├── Technical Structure
│   ├── Primary Key
│   ├── Columns (with business context)
│   ├── Relationships
│   └── Constraints
├── Business Context
│   ├── Display Name
│   ├── Description
│   ├── Business Purpose
│   └── Business Rules
├── Enhanced Metadata
│   ├── Properties
│   ├── Tags
│   └── Classification
└── TF-IDF Vectors
    └── Quick reference vectors

Individual Documents (Linked by TABLE)
├── TABLE_COLUMNS
├── RELATIONSHIPS
├── VIEWS
└── METRICS

TABLE_DOCUMENTs (Separate for Natural Language Search)
├── Rich Business Descriptions
├── Enhanced Column Context
├── Searchable Text Content
├── Business Keywords
└── Technical Keywords

TABLE_COLUMN Documents (Using helper.py functionality)
├── Column Definitions with Comments
├── Properties Integration
├── Field Type Classification
├── Business Context
└── Technical Context
```

## 🚀 Key Features

### ✅ Eliminates Duplication
- Single TABLE_SCHEMA document per table
- No more overlapping TABLE content types
- Clear separation of technical vs. business information

### ✅ Enhanced Search Capabilities
- TF-IDF vectors for semantic search
- Quick reference lookups by table name
- Document type filtering
- Similarity scoring
- **Natural language search** for tables and business context
- **Domain-based search** for business domains
- **Usage type search** for specific use cases
- **Field type classification** (dimension vs fact) for better query building
- **Query optimization** with performance suggestions
- **LLM-powered intelligence** for advanced field classification and query optimization
- **Context-aware recommendations** based on business requirements
- **Performance and indexing optimization** (SQL generation handled by existing SQL pairs and instructions)
- **TABLE_COLUMN documents** with helper.py integration for column definitions and comments

### ✅ Business Context Integration
- Rich business descriptions
- Usage guidelines and examples
- Privacy classifications
- Business rules and validation

### ✅ Backward Compatibility
- Maintains existing retrieval patterns
- Compatible with current helper utilities
- Gradual migration path

## 📋 Usage

### Basic Usage

```python
from agents.app.indexing2 import StorageManager
from langchain_openai import OpenAIEmbeddings
import chromadb

# Initialize components
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
persistent_client = chromadb.PersistentClient(path="./chroma_db")
doc_store = chromadb.DocumentChromaStore(
    persistent_client=persistent_client,
    collection_name="unified_storage"
)

# Create storage manager
storage_manager = StorageManager(
    document_store=doc_store,
    embedder=embeddings,
    enable_tfidf=True
)

# Process MDL
result = await storage_manager.process_mdl(mdl_str, project_id="my_project")
```

### Advanced Search

```python
# Search by table name
user_refs = await storage_manager.search_by_table_name("users", "my_project")

# Search by document type
schema_refs = await storage_manager.search_by_document_type("TABLE_SCHEMA", "my_project")

# Find similar documents
similar_docs = await storage_manager.find_similar_documents(
    "user account management",
    top_k=5,
    threshold=0.1
)

# Natural language search for tables
user_tables = await storage_manager.search_tables_by_natural_language(
    "user account management authentication",
    project_id="my_project",
    top_k=5
)

# Search by business domain
customer_tables = await storage_manager.search_tables_by_domain(
    "customer",
    project_id="my_project",
    top_k=3
)

# Search by usage type
analytics_tables = await storage_manager.search_tables_by_usage_type(
    "analytics",
    project_id="my_project",
    top_k=3
)

# Build optimized queries using field type classification
analytical_query = await storage_manager.build_query_for_table(
    table_name="sales",
    project_id="my_project",
    query_type="analytical",
    filters={"region": "North America"},
    aggregations=["SUM", "COUNT"],
    group_by=["product_category"],
    limit=10
)

# Get query suggestions based on field types
query_suggestions = await storage_manager.get_query_suggestions(
    table_name="users",
    project_id="my_project",
    field_type="fact"
)

# LLM-powered field classification
classification_result = await storage_manager.classify_columns_with_llm(
    table_name="sales",
    project_id="my_project",
    llm_client=your_llm_client  # Optional LLM client
)

# LLM-powered query optimization
optimization_result = await storage_manager.optimize_query_with_llm(
    query="SELECT * FROM sales WHERE region = 'North America'",
    table_name="sales",
    project_id="my_project",
    optimization_level="advanced",
    llm_client=your_llm_client  # Optional LLM client
)

# LLM-powered performance analysis
performance_analysis = await storage_manager.analyze_query_performance_with_llm(
    query="SELECT COUNT(*) FROM sales GROUP BY product_category",
    table_name="sales",
    project_id="my_project",
    performance_metrics={"execution_time": 2.5, "rows_processed": 5000},
    llm_client=your_llm_client  # Optional LLM client
)

# LLM-powered indexing strategy
indexing_strategy = await storage_manager.suggest_indexing_strategy_with_llm(
    table_name="sales",
    project_id="my_project",
    query_patterns=[
        "SELECT * FROM sales WHERE region = ?",
        "SELECT COUNT(*) FROM sales GROUP BY product_category",
        "SELECT * FROM sales WHERE order_date >= ?"
    ],
    performance_requirements={"max_query_time": 1.0, "concurrent_users": 50},
    llm_client=your_llm_client  # Optional LLM client
)

# Create TABLE_COLUMN documents with helper.py functionality
table_column_docs = await storage_manager._ddl_chunker.create_table_column_documents(
    mdl=mdl_data,
    project_id="my_project"
)
# Returns: List of TABLE_COLUMN documents with column definitions and comments
```

### TF-IDF Capabilities

```python
# Get TF-IDF statistics
tfidf_stats = await storage_manager.get_tfidf_stats()

# Get quick lookup statistics
lookup_stats = await storage_manager.get_quick_lookup_stats()
```

## 🔄 Migration from Current System

### Before (Duplicated)
```python
# Old system created duplicate documents
TABLE_SCHEMA documents containing TABLE content
TABLE_DESCRIPTION documents containing TABLE content (DUPLICATE!)
```

### After (Unified)
```python
# New system eliminates duplication
TABLE_SCHEMA documents with complete table information
Individual documents for specific types (TABLE_COLUMNS, RELATIONSHIPS, etc.)
```

### Migration Steps

1. **Update Document Creation**
   ```python
   # OLD
   metadata = {"type": "TABLE_SCHEMA", "name": "users"}
   content = {"type": "TABLE", "name": "users"}
   
   # NEW
   metadata = {"type": "TABLE_SCHEMA", "name": "users"}
   content = {"type": "TABLE_SCHEMA", "table_name": "users", "columns": [...], "business_context": [...]}
   ```

2. **Update Retrieval Queries**
   ```python
   # OLD
   where = {"type": "TABLE_SCHEMA", "name": {"$in": table_names}}
   
   # NEW (same query, enhanced content)
   where = {"type": "TABLE_SCHEMA", "name": {"$in": table_names}}
   ```

3. **Leverage New Features**
   ```python
   # Use TF-IDF search
   similar_docs = await storage_manager.find_similar_documents(query_text)
   
   # Use quick reference lookup
   table_refs = await storage_manager.search_by_table_name("users")
   ```

## 📊 Benefits

### Performance
- **Faster Retrieval** - TF-IDF vectors enable quick lookups
- **Reduced Storage** - Eliminates duplicate documents
- **Efficient Search** - Semantic search capabilities

### Maintainability
- **Clear Structure** - Single source of truth per table
- **Enhanced Metadata** - Rich business context
- **Type Safety** - Standardized document structures

### Functionality
- **Advanced Search** - Similarity scoring and semantic search
- **Business Context** - Rich descriptions and usage guidelines
- **Quick Lookups** - Fast reference by table name or document type

## 🧪 Testing

Run the example to test the system:

```python
from agents.app.indexing2.example_usage import ExampleUsage

example = ExampleUsage()
await example.run_example()
```

## 🔧 Configuration

### TF-IDF Configuration
```python
tfidf_config = {
    "max_features": 5000,
    "ngram_range": (1, 2),
    "min_df": 1,
    "max_df": 0.95,
    "stop_words": "english"
}
```

### Storage Configuration
```python
storage_config = {
    "column_batch_size": 200,
    "enable_tfidf": True,
    "tfidf_config": tfidf_config
}
```

## 📈 Future Enhancements

- **Vector Search Integration** - Combine TF-IDF with embedding vectors
- **Real-time Updates** - Incremental TF-IDF updates
- **Advanced Analytics** - Document similarity analytics
- **Caching Layer** - Redis integration for fast lookups

## 🤝 Contributing

When adding new features:

1. Maintain backward compatibility
2. Add comprehensive tests
3. Update documentation
4. Follow the established patterns

## 📝 Notes

- This system is designed to replace the current indexing system gradually
- All existing functionality is preserved while eliminating duplication
- TF-IDF generation is optional but recommended for enhanced search
- The system is fully compatible with existing helper utilities
