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
        """Convert table descriptions to documents."""
        logger.info(f"Starting table description chunking for project: {project_id}")
        
        def _additional_meta() -> Dict[str, Any]:
            return {"project_id": project_id} if project_id else {}

        # Get table descriptions
        logger.info("Extracting table descriptions from MDL")
        table_descriptions = self._get_table_descriptions(mdl)
        logger.info(f"Found {len(table_descriptions)} table descriptions")

        # Create chunks
        logger.info("Creating document chunks")
        chunks = []
        for chunk in table_descriptions:
            # Create stringified dictionary content (compatible with ast.literal_eval)
            content_dict = {
                "name": chunk['name'],
                "mdl_type": chunk['mdl_type'],
                "type": "TABLE_DESCRIPTION",
                "description": chunk['description'],
                "columns": ', '.join(chunk['columns']) if isinstance(chunk['columns'], list) else str(chunk['columns'])
            }

            # Add relationships if they exist
            if chunk.get('relationships'):
                content_dict["relationships"] = chunk['relationships']

            # Convert to stringified dictionary
            page_content = str(content_dict)
            
            # Debug logging
            logger.info(f"Created page content for {chunk['name']}:")
            logger.info(f"Description in content: {chunk['description'][:100]}...")
            logger.info(f"Page content preview: {page_content[:200]}...")
            
            chunks.append({
                "page_content": page_content,
                "metadata": {
                    "type": "TABLE_DESCRIPTION",
                    "mdl_type": chunk["mdl_type"],
                    "name": chunk["name"],
                    "description": chunk["description"],
                    "relationships": chunk.get("relationships", []),
                    **_additional_meta(),
                }
            })
        
        logger.info(f"Created {len(chunks)} document chunks")
        

        # Convert to Langchain documents
        logger.info("Converting chunks to Langchain documents")
        documents = [
            LangchainDocument(**chunk)
            for chunk in tqdm(
                chunks,
                desc=f"Project ID: {project_id}, Converting chunks to documents",
            )
        ]
        logger.info(f"Successfully converted {len(documents)} chunks to documents")

        return {"documents": documents}

    def _get_table_descriptions(self, mdl: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract table descriptions from MDL."""
        logger.info("Starting table description extraction from MDL")
        
        def _structure_data(mdl_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "mdl_type": mdl_type,
                "name": payload.get("name"),
                "description": payload.get("description", ""),
                "columns": [column["name"] for column in payload.get("columns", [])],
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
                
                description = {
                    "name": table_name,
                    "mdl_type": resource["mdl_type"],
                    "type": "TABLE_DESCRIPTION",
                    "description": resource.get("description", ""),
                    "columns": ", ".join(resource["columns"]),
                    "relationships": table_rels
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
            mdl = json.loads(mdl)
            logger.info("MDL string parsed successfully")
            logger.info("mdl: ", mdl)
            
            # Convert to documents
            logger.info("Converting MDL to documents")
            doc_result = await self._chunker.run(
                mdl=mdl,
                project_id=project_id,
            )
            logger.info(f"Created {len(doc_result['documents'])} documents")
            
            # Prepare documents for ChromaDB
            logger.info("Preparing documents for ChromaDB")
            documents = []
            for doc in doc_result["documents"]:
                # Create a new LangchainDocument with the embedding
                new_doc = LangchainDocument(
                    page_content=doc.page_content,
                    metadata=doc.metadata
                )
                logger.info("new_doc: ", new_doc.metadata)
                print("new_doc: ", new_doc.metadata)
                documents.append(new_doc)
                
            logger.info(f"Prepared {len(documents)} documents with embeddings")
            # Write documents to store
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
