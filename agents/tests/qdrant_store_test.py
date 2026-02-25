"""
LangChain Qdrant Query Client with Metadata Filtering
Supports filtering by type, project_id, and semantic search

Updated to use DocumentQdrantStore and settings similar to project_reader_qdrant.py
"""

from typing import List, Dict, Optional, Any
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
import logging

from app.storage.qdrant_store import DocumentQdrantStore, QDRANT_AVAILABLE
from app.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SchemaQueryClient:
    """
    LangChain-based query client for Qdrant with metadata filtering
    
    Features:
    - Search by natural language query
    - Filter by type (TABLE_DESCRIPTION, COLUMN_DESCRIPTION, etc.)
    - Filter by project_id (cornerstone, hr_compliance_risk, etc.)
    - Combine filters for precise queries
    - Return structured results with metadata
    
    Uses DocumentQdrantStore and settings similar to project_reader_qdrant.py
    """
    
    def __init__(
        self,
        collection_name: str = "table_descriptions",
        qdrant_url: Optional[str] = None,
        qdrant_host: Optional[str] = None,
        qdrant_port: Optional[int] = None,
        qdrant_client: Optional[QdrantClient] = None,
        openai_api_key: Optional[str] = None,
        embedding_model: Optional[str] = None,
        collection_prefix: Optional[str] = None
    ):
        """
        Initialize the query client
        
        Args:
            collection_name: Qdrant collection name (without prefix)
            qdrant_url: Qdrant cloud URL (if using Qdrant cloud)
            qdrant_host: Qdrant host for local instance (defaults to settings.QDRANT_HOST)
            qdrant_port: Qdrant port for local instance (defaults to settings.QDRANT_PORT)
            qdrant_client: Optional pre-initialized QdrantClient
            openai_api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
            embedding_model: OpenAI embedding model to use (defaults to settings.EMBEDDING_MODEL)
            collection_prefix: Prefix for collection names (defaults to "core_")
        """
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "Qdrant dependencies not installed. Install with: pip install qdrant-client langchain-qdrant"
            )
        
        # Use settings default for collection_prefix if not provided
        """
        if collection_prefix is None:
            collection_prefix = getattr(settings, "CORE_COLLECTION_PREFIX", "core_")
        """
        
        self.collection_prefix = collection_prefix
        self.collection_name = f"{collection_prefix}{collection_name}" if collection_prefix else collection_name
        
        # Initialize Qdrant client
        if qdrant_client is not None:
            self.qdrant_client = qdrant_client
        elif qdrant_url:
            self.qdrant_client = QdrantClient(url=qdrant_url)
        else:
            host = qdrant_host or getattr(settings, "QDRANT_HOST", None) or "localhost"
            port = qdrant_port or getattr(settings, "QDRANT_PORT", 6333)
            self.qdrant_client = QdrantClient(host=host, port=port)
        
        # Initialize embeddings
        api_key = openai_api_key or getattr(settings, "OPENAI_API_KEY", None)
        model = embedding_model or getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
        
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=api_key,
            model=model
        )
        
        # Initialize DocumentQdrantStore (similar to project_reader_qdrant.py)
        self.document_store = DocumentQdrantStore(
            qdrant_client=self.qdrant_client,
            collection_name=self.collection_name,
            embeddings_model=self.embeddings,
            host=None,  # Already have client
            port=None   # Already have client
        )
        
        # Keep reference to vectorstore for backward compatibility
        self.vectorstore = self.document_store.vectorstore
        print(f"Initialized SchemaQueryClient for collection: {self.collection_name}")
        logger.info(f"Initialized SchemaQueryClient for collection: {self.collection_name}")
    
    
    def _create_filter(
        self,
        type_filter: Optional[str] = None,
        project_id: Optional[str] = None,
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Filter]:
        """
        Create Qdrant filter from metadata criteria
        
        Args:
            type_filter: Filter by type (e.g., 'TABLE_DESCRIPTION')
            project_id: Filter by project_id (e.g., 'hr_compliance_risk')
            additional_filters: Additional metadata filters {field: value}
        
        Returns:
            Qdrant Filter object or None
        """
        conditions = []
        
        # Add type filter
        if type_filter:
            conditions.append(
                FieldCondition(
                    key="metadata.type",
                    match=MatchValue(value=type_filter)
                )
            )
        
        # Add project_id filter
        if project_id:
            conditions.append(
                FieldCondition(
                    key="metadata.source",
                    match=MatchValue(value=project_id)
                )
            )
        
        # Add additional filters
        if additional_filters:
            for field, value in additional_filters.items():
                conditions.append(
                    FieldCondition(
                        key=f"metadata.{field}",
                        match=MatchValue(value=value)
                    )
                )
        
        # Return filter only if conditions exist
        if conditions:
            return Filter(must=conditions)
        return None
    
    
    def search(
        self,
        query: str,
        type_filter: Optional[str] = None,
        project_id: Optional[str] = None,
        k: int = 5,
        score_threshold: Optional[float] = None,
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Search for documents using semantic similarity with optional filters
        
        Args:
            query: Natural language search query
            type_filter: Filter by document type (e.g., 'TABLE_DESCRIPTION')
            project_id: Filter by project (e.g., 'hr_compliance_risk')
            k: Number of results to return
            score_threshold: Minimum similarity score (0.0 - 1.0)
            additional_filters: Additional metadata filters
        
        Returns:
            List of Document objects with content and metadata
        
        Example:
            # Search for table schemas in hr_compliance_risk project
            results = client.search(
                query="skill gap analysis",
                type_filter="TABLE_DESCRIPTION",
                project_id="hr_compliance_risk",
                k=3
            )
        """
        # Build where clause for DocumentQdrantStore.semantic_search
        where_clause = {}
        if project_id:
            where_clause["source"] = project_id
        if type_filter:
            where_clause["type"] = type_filter
        if additional_filters:
            where_clause.update(additional_filters)
        
        logger.info(f"Searching with query: '{query}', where: {where_clause}, k: {k}")
        where_clause = None
        # Use DocumentQdrantStore.semantic_search (similar to project_reader_qdrant.py)
        search_results = self.document_store.semantic_search(
            query=query,
            k=k * 3 if score_threshold else k,  # Get more results if filtering by threshold
            where=where_clause if where_clause else None
        )
        
        # Convert results to LangChain Document format
        documents = []
        for result in search_results:
            score = result.get("score", 0.0)
            
            # Apply score threshold if specified
            if score_threshold and score < score_threshold:
                continue
            
            # Create LangChain Document
            doc = Document(
                page_content=result.get("content", "") or result.get("data", ""),
                metadata=result.get("metadata", {})
            )
            documents.append(doc)
            
            if len(documents) >= k:
                break
        
        print(f"Found {len(documents)} results")
        import json
        from pathlib import Path
        from datetime import datetime
        
        # Create output directory if it doesn't exist
        output_dir = Path("qdrant_response_dumps")
        output_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"qdrant_response_{timestamp}.json"
        
        # Prepare full response data
        response_data = {
            "query": query,
            "where_clause": where_clause,
            "k": k,
            "score_threshold": score_threshold,
            "total_results": len(search_results),
            "total_documents": len(documents),
            "raw_search_results": search_results,  # Raw Qdrant results
            "converted_documents": [
                {
                    "page_content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in documents
            ]
        }
        
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=2, default=str, ensure_ascii=False)
        
        logger.info(f"Full Qdrant response dumped to: {filename}")
        print(f"Full Qdrant response dumped to: {filename}")
        
        # Also print summary to console
        for i, doc in enumerate(documents[:3], 1):  # Print first 3 only
            print(f"\nDocument {i}:")
            print(f"  Metadata keys: {list(doc.metadata.keys())}")
            print(f"  Content length: {len(doc.page_content)}")
            print(f"  Content preview: {doc.page_content[:200]}...")
        
        logger.info(f"Found {len(documents)} results")
        return documents
    
    
    def search_tables(
        self,
        query: str,
        project_id: Optional[str] = None,
        k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        """
        Search specifically for table schemas
        
        Args:
            query: Search query
            project_id: Filter by project
            k: Number of results
            score_threshold: Minimum score
        
        Returns:
            List of table schema documents
        """
        return self.search(
            query=query,
            type_filter="TABLE_DESCRIPTION",
            project_id=project_id,
            k=k,
            score_threshold=score_threshold
        )
    
    
    def get_tables_by_project(
        self,
        project_id: str,
        k: int = 20
    ) -> List[Document]:
        """
        Get all tables for a specific project
        
        Args:
            project_id: Project identifier
            k: Max number of results
        
        Returns:
            List of table documents
        """
        # Use a generic query that should match all tables
        return self.search(
            query="table schema",
            type_filter="TABLE_DESCRIPTION",
            project_id=project_id,
            k=k,
            score_threshold=0.0  # No threshold to get all
        )
    
    
    def get_table_by_name(
        self,
        table_name: str,
        project_id: Optional[str] = None
    ) -> Optional[Document]:
        """
        Get a specific table by name
        
        Args:
            table_name: Name of the table
            project_id: Optional project filter
        
        Returns:
            Document or None if not found
        """
        additional_filters = {"name": table_name}
        
        results = self.search(
            query=table_name,
            type_filter="TABLE_DESCRIPTION",
            project_id=project_id,
            k=1,
            additional_filters=additional_filters
        )
        
        return results[0] if results else None
    
    
    def search_related_tables(
        self,
        query: str,
        primary_table: str,
        project_id: Optional[str] = None,
        k: int = 5
    ) -> List[Document]:
        """
        Find tables related to a primary table based on query
        
        Args:
            query: Search query describing relationship
            primary_table: Name of primary table
            project_id: Filter by project
            k: Number of results
        
        Returns:
            List of related table documents
        
        Example:
            # Find tables related to user_skill_proficiency
            results = client.search_related_tables(
                query="join required skills role requirements",
                primary_table="user_skill_proficiency",
                project_id="hr_compliance_risk"
            )
        """
        # Enhance query with primary table context
        enhanced_query = f"{query} related to {primary_table}"
        
        results = self.search_tables(
            query=enhanced_query,
            project_id=project_id,
            k=k + 1  # Get extra to filter out primary table
        )
        
        # Filter out the primary table itself
        related = [doc for doc in results if doc.metadata.get('name') != primary_table]
        return related[:k]
    
    
    def format_results(
        self,
        documents: List[Document],
        include_relationships: bool = True,
        include_query_patterns: bool = True,
        include_use_cases: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Format search results into structured dictionary
        
        Args:
            documents: List of Document objects
            include_relationships: Include relationship info
            include_query_patterns: Include query patterns
            include_use_cases: Include use cases
        
        Returns:
            List of formatted dictionaries
        """
        formatted = []
        
        for doc in documents:
            metadata = doc.metadata
            
            result = {
                'table_name': metadata.get('name', ''),
                'description': metadata.get('description', ''),
                'project_id': metadata.get('project_id', ''),
                'type': metadata.get('type', ''),
            }
            
            if include_relationships:
                result['relationships'] = metadata.get('relationships', [])
            
            if include_query_patterns:
                result['query_patterns'] = metadata.get('query_patterns', [])
            
            if include_use_cases:
                result['use_cases'] = metadata.get('use_cases', [])
            
            formatted.append(result)
        
        return formatted
    
    
    def get_project_summary(self, project_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a project
        
        Args:
            project_id: Project identifier
        
        Returns:
            Dictionary with project statistics
        """
        tables = self.get_tables_by_project(project_id, k=100)
        
        summary = {
            'project_id': project_id,
            'total_tables': len(tables),
            'table_names': [doc.metadata.get('name') for doc in tables],
            'has_relationships': sum(
                1 for doc in tables 
                if doc.metadata.get('relationships', [])
            )
        }
        
        return summary


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_query_client(
    collection_name: str = "table_descriptions",
    qdrant_url: Optional[str] = None,
    qdrant_host: Optional[str] = None,
    qdrant_port: Optional[int] = None,
    qdrant_client: Optional[QdrantClient] = None,
    openai_api_key: Optional[str] = None,
    embedding_model: Optional[str] = None,
    collection_prefix: Optional[str] = None
) -> SchemaQueryClient:
    """
    Factory function to create query client
    
    Uses settings from app.settings similar to project_reader_qdrant.py
    
    Example:
        client = create_query_client(
            collection_name="table_descriptions",
            collection_prefix="core_"
        )
    """
    # Use settings defaults if not provided
    if collection_prefix is None:
        collection_prefix = getattr(settings, "CORE_COLLECTION_PREFIX", "core_")
    
    return SchemaQueryClient(
        collection_name=collection_name,
        qdrant_url=qdrant_url,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        qdrant_client=qdrant_client,
        openai_api_key=openai_api_key,
        embedding_model=embedding_model,
        collection_prefix=collection_prefix
    )


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

def example_usage():
    """
    Example usage patterns
    
    Uses settings from app.settings similar to project_reader_qdrant.py
    """
    
    # Initialize client (uses settings defaults)
    client = SchemaQueryClient(
        collection_name="leen_table_description",
        collection_prefix=""
    )
    
    # =========================================================================
    # Example 1: Search for tables in specific project
    # =========================================================================
    print("Example 1: Search tables in hr_compliance_risk project")
    results = client.search_tables(
        query="vulnerabilities patch_compliance cve_exposure How do I calculate mean time to remediate critical vulnerabilities using Qualys data? Show me what tables are available.",
        #project_id="qualys",
        k=20
    )
    if results:
        for doc in results:
            print(f"  - {doc.metadata['name']}")
            print(f"    {doc.metadata['description'][:100]}...")
    else:
        print("No results found")
    
    # =========================================================================
    # Example 2: Get all tables for a project
    # =========================================================================
    print("\nExample 2: Get all tables for cornerstone project")
    tables = client.get_tables_by_project("cornerstone", k=10)
    print(f"Found {len(tables)} tables")
    for doc in tables:
        print(f"  - {doc.metadata['name']}")
    
    # =========================================================================
    # Example 3: Find specific table by name
    # =========================================================================
    """
    print("\nExample 3: Find specific table")
    table = client.get_table_by_name(
        table_name="user_skill_proficiency",
        project_id="qualys"
    )
    
    if table:
        print(f"Found: {table.metadata['name']}")
        print(f"Query patterns: {table.metadata['query_patterns']}")
    """
    # =========================================================================
    # Example 4: Search with multiple filters
    # =========================================================================
    print("\nExample 4: Search with filters and threshold")
    results = client.search(
        query="training completion status",
        type_filter="TABLE_DESCRIPTION",
        project_id="qualys",
        k=5,
        score_threshold=0.5  # Only high-confidence matches
    )
    
    formatted = client.format_results(results)
    for item in formatted:
        print(f"  - {item['table_name']}: {len(item['relationships'])} relationships")
    
    # =========================================================================
    # Example 5: Find related tables
    # =========================================================================
    print("\nExample 5: Find tables related to user_skill_proficiency")
    related = client.search_related_tables(
        query="Vulnerabilities patch_compliance cve_exposure How do I calculate mean time to remediate critical vulnerabilities using Qualys data? Show me what tables are available.",
        primary_table="qualys_vulnerabilities_api_2_0_fo_scan_summary_scan_summary",
        project_id="qualys",
        k=3
    )
    
    for doc in related:
        print(f"  - {doc.metadata['name']}")
        rels = doc.metadata.get('relationships', [])
        for rel in rels:
            if 'user_skill_proficiency' in rel.get('models', []):
                print(f"    Relationship: {rel.get('name')}")
    
    # =========================================================================
    # Example 6: Project summary
    # =========================================================================
    print("\nExample 6: Project summary")
    summary = client.get_project_summary("hr_compliance_risk")
    print(f"Project: {summary['project_id']}")
    print(f"Total tables: {summary['total_tables']}")
    print(f"Tables with relationships: {summary['has_relationships']}")


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("LangChain Qdrant Query Client - Usage Examples")
    print("=" * 80)
    print(f"\nUsing settings:")
    print(f"  QDRANT_HOST: {getattr(settings, 'QDRANT_HOST', 'localhost')}")
    print(f"  QDRANT_PORT: {getattr(settings, 'QDRANT_PORT', 6333)}")
    print(f"  EMBEDDING_MODEL: {getattr(settings, 'EMBEDDING_MODEL', 'text-embedding-3-small')}")
    print(f"  CORE_COLLECTION_PREFIX: {getattr(settings, 'CORE_COLLECTION_PREFIX', 'core_')}")
    print(f"  OPENAI_API_KEY: {'***' if getattr(settings, 'OPENAI_API_KEY', None) else 'Not set'}")
    
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        print("\nRunning examples...")
        example_usage()
    else:
        print("\nTo run examples, execute: python qdrant_store_test.py run")
        print("\nUncomment example_usage() in code to run examples programmatically")
        # example_usage()