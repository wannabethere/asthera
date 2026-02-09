import logging
import uuid
from typing import Any, Dict, List, Optional, Union

from tqdm import tqdm
from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")


class TableDescriptionChunker:
    """Chunks table descriptions from MDL into documents."""
    
    async def run(self, mdl: Dict[str, Any], project_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert table descriptions to documents with enriched metadata."""
        logger.info(f"Starting table description chunking for project: {project_id}")
        
        def _additional_meta() -> Dict[str, Any]:
            return {"project_id": project_id} if project_id else {}

        def _extract_query_patterns(chunk: Dict[str, Any]) -> List[str]:
            """Extract query patterns from table description, prioritizing MDL properties."""
            query_patterns = []
            name = chunk.get("name", "")
            description = chunk.get("description", "")
            mdl_type = chunk.get("mdl_type", "")
            
            # First, try to extract from chunk properties (from MDL)
            chunk_properties = chunk.get("properties", {})
            if chunk_properties:
                # Check for queryPatterns in properties (could be string or list)
                mdl_query_patterns = chunk_properties.get("queryPatterns") or chunk_properties.get("query_patterns")
                if mdl_query_patterns:
                    import json
                    if isinstance(mdl_query_patterns, str):
                        try:
                            query_patterns = json.loads(mdl_query_patterns)
                        except:
                            # If parsing fails, treat as single string
                            query_patterns = [mdl_query_patterns]
                    elif isinstance(mdl_query_patterns, list):
                        query_patterns = mdl_query_patterns
                    if query_patterns:
                        logger.debug(f"Using queryPatterns from MDL for {name}: {len(query_patterns)} patterns")
                        return query_patterns
            
            # Base query patterns (fallback)
            query_patterns.extend([
                f"What is the {name} table?",
                f"Describe the {name} table",
                f"What does {name} contain?",
                f"Explain the purpose of {name}"
            ])
            
            # Add type-specific patterns
            if mdl_type == "METRIC":
                query_patterns.extend([
                    f"What metrics are in {name}?",
                    f"What KPIs does {name} provide?",
                    f"Show me the metric definition for {name}"
                ])
            elif mdl_type == "VIEW":
                query_patterns.extend([
                    f"What is the {name} view?",
                    f"What data does {name} view contain?",
                    f"Describe the {name} view"
                ])
            
            # Add relationship-based patterns
            if chunk.get("relationships"):
                query_patterns.extend([
                    f"What are the relationships for {name}?",
                    f"What tables does {name} connect to?",
                    f"Show me joins involving {name}"
                ])
            
            return query_patterns

        def _extract_use_cases(chunk: Dict[str, Any]) -> List[str]:
            """Extract use cases from table description, prioritizing MDL properties."""
            use_cases = []
            name = chunk.get("name", "")
            mdl_type = chunk.get("mdl_type", "")
            description = chunk.get("description", "")
            
            # First, try to extract from chunk properties (from MDL)
            chunk_properties = chunk.get("properties", {})
            if chunk_properties:
                # Check for useCases in properties (could be string or list)
                # Also check for complianceUseCases for backward compatibility
                mdl_use_cases = (chunk_properties.get("useCases") or 
                                chunk_properties.get("use_cases") or
                                chunk_properties.get("complianceUseCases"))
                if mdl_use_cases:
                    import json
                    if isinstance(mdl_use_cases, str):
                        try:
                            use_cases = json.loads(mdl_use_cases)
                        except:
                            # If parsing fails, treat as single string
                            use_cases = [mdl_use_cases]
                    elif isinstance(mdl_use_cases, list):
                        use_cases = mdl_use_cases
                    if use_cases:
                        logger.debug(f"Using useCases from MDL for {name}: {len(use_cases)} use cases")
                        return use_cases
            
            # Base use cases (fallback)
            use_cases.extend([
                "Table exploration and discovery",
                "Schema understanding and documentation",
                "Data model analysis"
            ])
            
            # Add type-specific use cases
            if mdl_type == "METRIC":
                use_cases.extend([
                    "Business intelligence and analytics",
                    "KPI tracking and reporting",
                    "Performance measurement",
                    "Dashboard creation"
                ])
            elif mdl_type == "VIEW":
                use_cases.extend([
                    "Precomputed query access",
                    "Data aggregation and summarization",
                    "Simplified data access patterns"
                ])
            
            # Add relationship-based use cases
            if chunk.get("relationships"):
                use_cases.extend([
                    "Join path discovery",
                    "Relationship mapping",
                    "Data lineage analysis"
                ])
            
            return use_cases

        # Get table descriptions
        logger.info("Extracting table descriptions from MDL")
        table_descriptions = self._get_table_descriptions(mdl)
        logger.info(f"Found {len(table_descriptions)} table descriptions")

        # Create chunks with enriched metadata
        logger.info("Creating document chunks with enriched metadata")
        chunks = []
        for chunk in table_descriptions:
            # Extract query patterns and use cases
            query_patterns = _extract_query_patterns(chunk)
            use_cases = _extract_use_cases(chunk)
            
            # Create stringified dictionary content (compatible with ast.literal_eval)
            # Preserve full column information (name, comment, description)
            columns_data = chunk.get('columns', [])
            # Create comma-separated string for backward compatibility
            columns_string = ', '.join(
                [col["name"] if isinstance(col, dict) else str(col) for col in columns_data]
            ) if columns_data else ""
            
            content_dict = {
                "name": chunk['name'],
                "mdl_type": chunk['mdl_type'],
                "type": "TABLE_DESCRIPTION",
                "description": chunk['description'],
                "columns": columns_data,  # Full column information with name, comment, description - stored in content
                "columns_string": columns_string,  # Comma-separated for backward compatibility
            }
            
            # Log columns to verify they're being included
            if columns_data:
                logger.info(f"Content dict for {chunk['name']} includes {len(columns_data)} columns in 'columns' field")
                logger.debug(f"Sample column data: {columns_data[0] if columns_data else 'None'}")
            else:
                logger.warning(f"WARNING: No columns data for {chunk['name']} - columns_data is empty!")

            # Add relationships if they exist
            if chunk.get('relationships'):
                content_dict["relationships"] = chunk['relationships']

            # Convert to stringified dictionary
            page_content = str(content_dict)
            
            # Build enriched text with query patterns and use cases
            enriched_text_parts = [page_content]
            
            if query_patterns:
                enriched_text_parts.append("\n\nANSWERS THESE QUESTIONS:")
                for pattern in query_patterns:
                    enriched_text_parts.append(f"  • {pattern}")
            
            if use_cases:
                enriched_text_parts.append("\n\nUSE CASES AND APPLICATIONS:")
                for use_case in use_cases:
                    enriched_text_parts.append(f"  • {use_case}")
            
            enriched_text = "\n".join(enriched_text_parts)
            
            # Debug logging
            logger.info(f"Created page content for {chunk['name']}:")
            logger.info(f"Description in content: {chunk['description'][:100]}...")
            logger.info(f"Page content preview: {page_content[:200]}...")
            logger.info(f"Columns data for {chunk['name']}: {len(columns_data)} columns")
            if columns_data:
                logger.info(f"Sample columns: {[col.get('name', '') if isinstance(col, dict) else str(col) for col in columns_data[:3]]}")
            
            chunks.append({
                "id": str(uuid.uuid4()),
                "text": enriched_text,
                "page_content": page_content,
                "metadata": {
                    "type": "TABLE_DESCRIPTION",
                    "mdl_type": chunk["mdl_type"],
                    "name": chunk["name"],
                    "description": chunk["description"],
                    "columns": columns_data,  # Full column information with name, comment, description in metadata
                    "columns_string": columns_string,  # Comma-separated for backward compatibility
                    "relationships": chunk.get("relationships", []),
                    "query_patterns": query_patterns,
                    "use_cases": use_cases,
                    **_additional_meta(),
                }
            })
            
            # Log metadata to verify columns are included
            logger.debug(f"Metadata for {chunk['name']} includes columns: {'columns' in chunks[-1]['metadata']}")
            if 'columns' in chunks[-1]['metadata']:
                logger.debug(f"Columns in metadata: {len(chunks[-1]['metadata']['columns'])} items")
        
        logger.info(f"Created {len(chunks)} document chunks with enriched metadata")
        

        # Convert to Langchain documents (for compatibility)
        logger.info("Converting chunks to Langchain documents")
        documents = [
            LangchainDocument(
                page_content=chunk["page_content"],
                metadata=chunk["metadata"]
            )
            for chunk in tqdm(
                chunks,
                desc=f"Project ID: {project_id}, Converting chunks to documents",
            )
        ]
        logger.info(f"Successfully converted {len(documents)} chunks to documents")

        return {
            "documents": documents,
            "points_data": chunks  # Also return points_data for direct Qdrant insertion
        }

    def _get_table_descriptions(self, mdl: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract table descriptions from MDL."""
        logger.info("Starting table description extraction from MDL")
        
        def _structure_data(mdl_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            # Preserve full column information with comments and descriptions
            columns_data = []
            for column in payload.get("columns", []):
                column_name = column.get("name", "")
                if not column_name:
                    continue
                
                # Extract column properties for comment/description
                column_properties = column.get("properties", {})
                display_name = column_properties.get("displayName", "")
                column_description = column_properties.get("description", "")
                
                # Build column data with name, comment (displayName), and description
                column_info = {
                    "name": column_name,
                    "comment": display_name,  # Use displayName as comment
                    "description": column_description,
                    "type": column.get("type", ""),  # Preserve data type
                }
                
                # Preserve other column properties if needed
                if column_properties:
                    column_info["properties"] = column_properties
                
                columns_data.append(column_info)
            
            return {
                "mdl_type": mdl_type,
                "name": payload.get("name"),
                "description": payload.get("description", ""),
                "columns": columns_data,  # Full column information instead of just names
                "properties": payload.get("properties", {}),
            }

        # Process models
        logger.info("Processing models")
        models = [_structure_data("TABLE_SCHEMA", model) for model in mdl.get("models", [])]
        logger.info(f"Processed {len(models)} models")

        # Process metrics
        logger.info("Processing metrics")
        metrics = [_structure_data("METRIC", metric) for metric in mdl.get("metrics", [])]
        logger.info(f"Processed {len(metrics)} metrics")

        # Process views
        logger.info("Processing views")
        views = [_structure_data("VIEW", view) for view in mdl.get("views", [])]
        logger.info(f"Processed {len(views)} views")

        # Process relationships
        logger.info("Processing relationships")
        relationships = mdl.get("relationships", [])
        logger.info(f"Processed {len(relationships)} relationships")

        # Create a mapping of table names to their relationships
        table_relationships = {}
        for relationship in relationships:
            models_in_relationship = relationship.get("models", [])
            for table_name in models_in_relationship:
                if table_name not in table_relationships:
                    table_relationships[table_name] = []
                table_relationships[table_name].append({
                    "name": relationship.get("name", ""),
                    "models": models_in_relationship,
                    "joinType": relationship.get("joinType", ""),
                    "condition": relationship.get("condition", ""),
                    "properties": relationship.get("properties", {})
                })

        # Combine all resources
        resources = models + metrics + views
        logger.info(f"Total resources found: {len(resources)}")

        # Create descriptions
        logger.info("Creating table descriptions")
        descriptions = []
        for resource in resources:
            if resource["name"] is not None:
                table_name = resource["name"]
                table_rels = table_relationships.get(table_name, [])
                
                # Debug logging
                logger.info(f"Processing resource: {table_name}")
                logger.info(f"Resource description: {resource.get('description', 'NO DESCRIPTION')}")
                
                # Preserve full column information (name, comment, description)
                # Keep both structured columns array and comma-separated string for backward compatibility
                columns_data = resource.get("columns", [])
                columns_string = ", ".join(
                    [col["name"] if isinstance(col, dict) else str(col) for col in columns_data]
                ) if columns_data else ""
                
                description = {
                    "name": table_name,
                    "mdl_type": resource["mdl_type"],
                    "type": "TABLE_DESCRIPTION",
                    "description": resource.get("description", ""),
                    "columns": columns_data,  # Full column information with name, comment, description
                    "columns_string": columns_string,  # Comma-separated for backward compatibility
                    "relationships": table_rels,
                    "properties": resource.get("properties", {})  # Include properties for queryPatterns/useCases extraction
                }
                descriptions.append(description)
                logger.info(f"Created description for {table_name}: {description['description'][:100]}...")
        
        logger.info(f"Created {len(descriptions)} table descriptions with relationships")
        
        return descriptions


class TableDescription:
    """Processes and indexes table descriptions from MDL."""
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
    ) -> None:
        """Initialize the Table Description processor."""
        logger.info("Initializing TableDescription processor")
        self._document_store = document_store
        self._embedder = embedder
        self._chunker = TableDescriptionChunker()
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )
        logger.info("TableDescription processor initialized successfully")

    async def run(
        self, mdl: Union[str, Dict], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process and index table descriptions."""
        logger.info(f"Starting table description processing for project: {project_id}")
        
        try:
            # Parse MDL string
            logger.info("Parsing MDL string")
            import json
            mdl = json.loads(mdl) if isinstance(mdl, str) else mdl
            logger.info("MDL string parsed successfully")
            
            # Convert to documents
            logger.info("Converting MDL to documents")
            doc_result = await self._chunker.run(
                mdl=mdl,
                project_id=project_id,
            )
            logger.info(f"Created {len(doc_result['documents'])} documents")
            
            # Check if document_store is Qdrant-based and use direct points
            from app.storage.qdrant_store import DocumentQdrantStore
            if isinstance(self._document_store, DocumentQdrantStore):
                logger.info("Using direct Qdrant points insertion for table descriptions")
                points_data = doc_result.get("points_data", [])
                if points_data:
                    # Verify columns are in points_data before writing to Qdrant
                    logger.info(f"Verifying columns in {len(points_data)} points before writing to Qdrant")
                    points_with_columns = 0
                    points_without_columns = 0
                    for point in points_data:
                        metadata = point.get("metadata", {})
                        if "columns" in metadata:
                            cols = metadata["columns"]
                            if cols and len(cols) > 0:
                                points_with_columns += 1
                                logger.debug(f"Point for '{metadata.get('name', 'unknown')}' has {len(cols)} columns in metadata")
                            else:
                                points_without_columns += 1
                                logger.warning(f"Point for '{metadata.get('name', 'unknown')}' has empty columns list")
                        else:
                            points_without_columns += 1
                            logger.warning(f"Point for '{metadata.get('name', 'unknown')}' does NOT have 'columns' in metadata. Keys: {list(metadata.keys())}")
                    
                    logger.info(f"Columns verification: {points_with_columns} points with columns, {points_without_columns} points without columns")
                    
                    write_result = self._document_store.add_points_direct(
                        points_data=points_data,
                        log_schema=True
                    )
                    logger.info(f"Successfully wrote {write_result['documents_written']} points to Qdrant")
                else:
                    # Fallback to documents if points_data not available
                    logger.warning("points_data not available, falling back to documents")
                    write_result = await self._writer.run(documents=doc_result["documents"], policy=DuplicatePolicy.SKIP)
            else:
                # Use standard document writer for ChromaDB
                logger.info("Using standard document writer for ChromaDB")
                documents = []
                for doc in doc_result["documents"]:
                    new_doc = LangchainDocument(
                        page_content=doc.page_content,
                        metadata=doc.metadata
                    )
                    documents.append(new_doc)
                
                logger.info(f"Prepared {len(documents)} documents")
                logger.info("Writing documents to store")
                write_result = await self._writer.run(documents=documents, policy=DuplicatePolicy.SKIP)
                logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "project_id": project_id
            }
            logger.info(f"Table description processing completed successfully: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing table descriptions: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error("Traceback: %s", traceback.format_exc())
            return {
                "documents_written": 0,
                "project_id": project_id,
                "error": str(e)
            }

    async def clean(self, project_id: Optional[str] = None) -> None:
        """Clean documents for the specified project."""
        logger.info(f"Starting cleanup for project: {project_id}")
        
        try:
            # Delete documents with the specified project_id
            if project_id:
                logger.info(f"Deleting documents for project ID: {project_id}")
                self._document_store.collection.delete(
                    where={"project_id": project_id}
                )
                logger.info(f"Successfully deleted documents for project ID: {project_id}")
            else:
                # Delete all documents if no project_id specified
                logger.info("Deleting all documents")
                self._document_store.collection.delete()
                logger.info("Successfully deleted all documents")
                
        except Exception as e:
            error_msg = f"Error cleaning documents: {str(e)}"
            logger.error(error_msg)
            raise


if __name__ == "__main__":
    # Example usage
    import chromadb
    from langchain_openai import OpenAIEmbeddings
    from agents.app.settings import get_settings
    
    logger.info("Initializing test environment")
    settings = get_settings()
    
    # Initialize embeddings
    logger.info("Initializing embeddings")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    # Initialize document store and processor
    logger.info("Initializing document store")
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    doc_store = DocumentChromaStore(
        persistent_client=persistent_client,
        collection_name="table_descriptions"
    )
    
    logger.info("Creating TableDescription processor")
    processor = TableDescription(
        document_store=doc_store,
        embedder=embeddings
    )
    
    # Example MDL string
    logger.info("Processing test MDL string")
    mdl_str = '{"models": [], "views": [], "relationships": [], "metrics": []}'
    
    # Process the table descriptions
    import asyncio
    logger.info("Starting test processing")
    result = asyncio.run(processor.run(mdl_str, project_id="test"))
    logger.info(f"Test processing completed: {result}")
