import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy

logger = logging.getLogger("genieml-agents")


class Instruction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instruction: str = ""
    question: str = ""
    sql: Optional[str] = None
    chain_of_thought: Optional[str] = None
    # This is used to identify the default instruction needed to be retrieved for the project
    is_default: bool = False


class InstructionsConverter:
    """Converts Instruction objects to LangchainDocument objects."""
    
    async def run(self, instructions: list[Instruction], project_id: Optional[str] = "") -> Dict[str, Any]:
        """Convert instructions to documents with enriched metadata."""
        logger.info(f"Project ID: {project_id} Converting instructions to documents...")

        def _extract_query_patterns(instruction: Instruction) -> List[str]:
            """Extract query patterns from instruction."""
            query_patterns = []
            
            if instruction.question:
                query_patterns.append(instruction.question)
            
            # Add patterns based on instruction content
            if instruction.instruction:
                query_patterns.extend([
                    f"How to {instruction.instruction.lower()}?",
                    f"What is the approach for {instruction.instruction.lower()}?",
                    f"Explain {instruction.instruction.lower()}"
                ])
            
            # Add generic patterns
            query_patterns.extend([
                "What instructions apply to this query?",
                "Show me relevant instructions",
                "What guidance is available for this?",
                "Find instructions for similar questions"
            ])
            
            return query_patterns

        def _extract_use_cases(instruction: Instruction) -> List[str]:
            """Extract use cases from instruction."""
            use_cases = [
                "Query guidance and instructions",
                "SQL generation assistance",
                "Question answering with context",
                "Instruction-based query processing",
                "Chain of thought reasoning"
            ]
            
            if instruction.is_default:
                use_cases.append("Default project instructions")
            
            return use_cases

        addition = {"project_id": project_id} if project_id else {}
        import json
        
        chunks = []
        for instruction in instructions:
            page_content = json.dumps({
                "type": "INSTRUCTION",
                "question": instruction.question,
                "sql": instruction.sql,
                "chain_of_thought": instruction.chain_of_thought,
                "is_default": instruction.is_default
            })
            
            query_patterns = _extract_query_patterns(instruction)
            use_cases = _extract_use_cases(instruction)
            
            # Build enriched text
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
            
            chunk = {
                "id": instruction.id,
                "text": enriched_text,
                "page_content": page_content,
                "metadata": {
                    "instruction_id": instruction.id,
                    "instruction": instruction.instruction,
                    "sql": instruction.sql,
                    "chain_of_thought": instruction.chain_of_thought,
                    "is_default": instruction.is_default,
                    "query_patterns": query_patterns,
                    "use_cases": use_cases,
                    **addition,
                }
            }
            chunks.append(chunk)
        
        return {
            "documents": [
                LangchainDocument(
                    page_content=chunk["page_content"],
                    metadata=chunk["metadata"]
                )
                for chunk in chunks
            ],
            "points_data": chunks  # Also return points_data for direct Qdrant insertion
        }


class Instructions:
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
    ) -> None:
        """Initialize the Instructions processor."""
        logger.info("Initializing Instructions processor")
        self._document_store = document_store
        self._embedder = embedder
        self._converter = InstructionsConverter()
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )
        logger.info("Instructions processor initialized successfully")

    async def run(
        self, instructions: list[Instruction], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process and index instructions."""
        logger.info(f"Starting instructions processing for project: {project_id}")
        
        try:
            # Convert to documents
            logger.info("Converting instructions to documents")
            doc_result = await self._converter.run(
                instructions=instructions,
                project_id=project_id,
            )
            logger.info(f"Created {len(doc_result['documents'])} documents")
            
            # Check if document_store is Qdrant-based and use direct points
            from app.storage.qdrant_store import DocumentQdrantStore
            if isinstance(self._document_store, DocumentQdrantStore):
                logger.info("Using direct Qdrant points insertion for instructions")
                points_data = doc_result.get("points_data", [])
                if points_data:
                    write_result = self._document_store.add_points_direct(
                        points_data=points_data,
                        log_schema=True
                    )
                    logger.info(f"Successfully wrote {write_result['documents_written']} points to Qdrant")
                else:
                    # Fallback to documents if points_data not available
                    logger.warning("points_data not available, falling back to documents")
                    write_result = await self._writer.run(documents=doc_result["documents"])
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
                write_result = await self._writer.run(documents=documents)
                logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "project_id": project_id
            }
            logger.info(f"Instructions processing completed successfully: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing instructions: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error("Traceback: %s", traceback.format_exc())
            return {
                "documents_written": 0,
                "project_id": project_id,
                "error": str(e)
            }

    async def clean(
        self,
        instructions: Optional[List[Instruction]] = None,
        project_id: Optional[str] = None,
        delete_all: bool = False,
    ) -> None:
        """Clean documents for the specified instructions or project."""
        logger.info(f"Starting cleanup for project: {project_id}")
        
        try:
            if delete_all:
                # Delete all documents if delete_all is True
                logger.info("Deleting all documents")
                self._document_store.collection.delete()
                logger.info("Successfully deleted all documents")
            elif project_id:
                # Delete documents with the specified project_id
                logger.info(f"Deleting documents for project ID: {project_id}")
                self._document_store.collection.delete(
                    where={"project_id": project_id}
                )
                logger.info(f"Successfully deleted documents for project ID: {project_id}")
            elif instructions:
                # Delete documents for specific instructions
                instruction_ids = [instruction.id for instruction in instructions]
                logger.info(f"Deleting documents for instruction IDs: {instruction_ids}")
                self._document_store.collection.delete(
                    where={"instruction_id": {"$in": instruction_ids}}
                )
                logger.info(f"Successfully deleted documents for instruction IDs: {instruction_ids}")
                
        except Exception as e:
            error_msg = f"Error cleaning documents: {str(e)}"
            logger.error(error_msg)
            raise


if __name__ == "__main__":
    # Example usage
    from langchain_openai import OpenAIEmbeddings
    from agents.app.settings import get_settings
    
    logger.info("Initializing test environment")
    settings = get_settings()
    
    logger.info("Initializing embeddings")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    # Initialize document store and processor
    logger.info("Initializing document store")
    doc_store = DocumentChromaStore(
        persistent_client=None,  # You'll need to provide the actual client
        collection_name="instructions"
    )
    
    logger.info("Creating Instructions processor")
    processor = Instructions(
        document_store=doc_store,
        embedder=embeddings
    )
    
    # Example instruction
    logger.info("Creating test instruction")
    instruction = Instruction(
        instruction="France is in the table of customers and the column is country",
        question="What is the capital of France?",
        sql="SELECT capital FROM countries WHERE country = 'France'",
        chain_of_thought="1. Look for France in the countries table\n2. Get the capital column"
    )
    
    # Process the instruction
    logger.info("Starting test processing")
    import asyncio

    result = asyncio.run(processor.run([instruction]))
    logger.info(f"Test processing completed: {result}")
