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
        """Convert instructions to documents."""
        logger.info(f"Project ID: {project_id} Converting instructions to documents...")

        addition = {"project_id": project_id} if project_id else {}
        import json
        return {
            "documents": [
                LangchainDocument(
                    page_content=json.dumps({"type":"INSTRUCTION", "question": instruction.question, "sql": instruction.sql, "chain_of_thought": instruction.chain_of_thought, "is_default": instruction.is_default}),
                    metadata={
                        "instruction_id": instruction.id,
                        "instruction": instruction.instruction,
                        "sql": instruction.sql,
                        "chain_of_thought": instruction.chain_of_thought,
                        "is_default": instruction.is_default,
                        **addition,
                    }
                )
                for instruction in instructions
            ]
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
            # Parse instructions string
            logger.info("Parsing instructions string")
            #import json
            #instructions = json.loads(instructions_str)
            #logger.info("Instructions string parsed successfully")
            
            # Convert to documents
            logger.info("Converting instructions to documents")
            doc_result = await self._converter.run(
                instructions=instructions,
                project_id=project_id,
            )
            for doc in doc_result["documents"]:
                print("doc in instructions: ", doc)
            logger.info(f"Created {len(doc_result['documents'])} documents")
            
            # Generate embeddings
            logger.info("Generating embeddings for documents")
            texts = [doc.page_content for doc in doc_result["documents"]]
            embeddings = await self._embedder.aembed_documents(texts)
            
            # Prepare documents for ChromaDB
            logger.info("Preparing documents for ChromaDB")
            documents = []
            for doc, embedding in zip(doc_result["documents"], embeddings):
                # Create a new LangchainDocument with the embedding
                new_doc = LangchainDocument(
                    page_content=doc.page_content,
                    metadata=doc.metadata
                )
                #new_doc.metadata["embedding"] = embedding
                documents.append(new_doc)
            for doc in documents:
                print("doc in instructions: ", doc)
            logger.info(f"Prepared {len(documents)} documents with embeddings")
            
            # Write documents to store
            logger.info("Writing documents to store")
            #write_result = await self._writer.run(documents=documents)
            #logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "project_id": project_id
            }
            logger.info(f"Instructions processing completed successfully: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing instructions: {str(e)}"
            logger.error(error_msg)
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
