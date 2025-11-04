import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Set

import orjson
from pydantic import BaseModel, Field
from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")


class SqlPair(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sql: str = ""
    question: str = ""
    instructions: Optional[str] = None
    chain_of_thought: Optional[str] = None


class SqlPairsConverter:
    """Converts SqlPair objects to LangchainDocument objects."""
    
    def run(self, sql_pairs: List[SqlPair], project_id: Optional[str] = "") -> Dict[str, Any]:
        """Convert SQL pairs to documents."""
        logger.info(f"Converting SQL pairs to documents for project: {project_id}")

        addition = {"project_id": project_id} if project_id else {}
        import json
        return {
            "documents": [
                LangchainDocument(
                    page_content=json.dumps({"type":"SQL_PAIR", "question": sql_pair.question, "sql": sql_pair.sql, "instructions": sql_pair.instructions, "chain_of_thought": sql_pair.chain_of_thought}),
                    metadata={
                        "sql_pair_id": sql_pair.id,
                        "sql": sql_pair.sql,
                        "instructions": sql_pair.instructions,
                        "chain_of_thought": sql_pair.chain_of_thought,
                        **addition,
                    }
                )
                for sql_pair in sql_pairs
            ]
        }


def _load_sql_pairs(sql_pairs_path: str) -> Dict[str, Any]:
    """Load SQL pairs from a JSON file."""
    if not sql_pairs_path:
        logger.warning("No SQL pairs path provided")
        return {}

    if not os.path.exists(sql_pairs_path):
        logger.warning(f"SQL pairs file not found: {sql_pairs_path}")
        return {}

    try:
        logger.info(f"Loading SQL pairs from: {sql_pairs_path}")
        with open(sql_pairs_path, "r") as file:
            data = orjson.loads(file.read())
            logger.info(f"Successfully loaded SQL pairs from {sql_pairs_path}")
            return data
    except Exception as e:
        logger.error(f"Error loading SQL pairs file: {e}")
        return {}


class SqlPairs:
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        sql_pairs_path: Optional[str] = "sql_pairs.json",
    ) -> None:
        """Initialize the SQL Pairs processor."""
        logger.info("Initializing SQL Pairs processor")
        self._document_store = document_store
        self._embedder = embedder
        self._converter = SqlPairsConverter()
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )
        self._external_pairs = _load_sql_pairs(sql_pairs_path)
        logger.info("SQL Pairs processor initialized successfully")

    def _extract_boilerplates(self, mdl_str: str) -> Set[str]:
        """Extract boilerplate names from MDL string."""
        logger.info("Extracting boilerplates from MDL")
        try:
            mdl = orjson.loads(mdl_str)
            boilerplates = {
                boilerplate.lower()
                for model in mdl.get("models", [])
                if (boilerplate := model.get("properties", {}).get("boilerplate"))
            }
            logger.info(f"Found {len(boilerplates)} boilerplates in MDL")
            return boilerplates
        except Exception as e:
            logger.error(f"Error extracting boilerplates: {e}")
            return set()

    def _create_sql_pairs(
        self, boilerplates: Set[str], external_pairs: Dict[str, Any]
    ) -> List[SqlPair]:
        """Create SQL pairs from boilerplates and external pairs."""
        logger.info("Creating SQL pairs from boilerplates and external pairs")
        pairs = []
        for boilerplate in boilerplates:
            if boilerplate in external_pairs:
                for pair in external_pairs[boilerplate]:
                    pairs.append(
                        SqlPair(
                            question=pair.get("question", ""),
                            sql=pair.get("sql", ""),
                            instructions=pair.get("instructions"),
                            chain_of_thought=pair.get("chain_of_thought")
                        )
                    )
        logger.info(f"Created {len(pairs)} SQL pairs")
        return pairs
    
    def _load_sql_pairs(self, sql_pairs_path: str,external_pairs: Optional[Dict[str, Any]] = {}) -> List[SqlPair]:
        """Load SQL pairs from a JSON file."""
        if not sql_pairs_path:
            logger.warning("No SQL pairs path provided")
            return []
        logger.info("Extracting boilerplates from MDL")
        boilerplates = self._extract_boilerplates(mdl_str)
        
        logger.info("Creating SQL pairs")
        sql_pairs = self._create_sql_pairs(
            boilerplates,
            {**self._external_pairs, **external_pairs}
        )
        logger.info(f"Created {len(sql_pairs)} SQL pairs")
        return sql_pairs       

    async def run(
        self,
        sql_pairs: List[Dict[str, Any]],
        project_id: Optional[str] = ""
    ) -> Dict[str, Any]:
        """Process and index SQL pairs."""
        logger.info(f"Starting SQL pairs processing for project: {project_id}")
        
        try:
            # Convert dictionaries to SqlPair objects
            logger.info("Converting SQL pair dictionaries to SqlPair objects")
            sql_pair_objects = [
                SqlPair(
                    question=pair.get("question", ""),
                    sql=pair.get("sql", ""),
                    instructions=pair.get("instructions"),
                    chain_of_thought=pair.get("chain_of_thought")
                )
                for pair in sql_pairs
            ]
            logger.info(f"Converted {len(sql_pair_objects)} SQL pairs to objects")
            
            # Convert to documents
            logger.info("Converting SQL pairs to documents")
            doc_result = self._converter.run(
                sql_pairs=sql_pair_objects,
                project_id=project_id,
            )
            logger.info(f"Converted {len(doc_result['documents'])} SQL pairs to documents")
            for doc in doc_result["documents"]:
                print("doc in run: ", doc)
            # Generate embeddings
            logger.info("Generating embeddings for documents")
            texts = [doc.page_content for doc in doc_result["documents"]]
            embeddings = await self._embedder.aembed_documents(texts)
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
                
            logger.info(f"Prepared {len(documents)} documents with embeddings")
            
            # Write documents to store
            logger.info("Writing documents to store")
            write_result = await self._writer.run(documents=documents)
            logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "project_id": project_id
            }
            logger.info(f"SQL pairs processing completed successfully: {result}")
            
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing SQL pairs: {str(e)}"
            logger.error(error_msg)
            return {
                "documents_written": 0,
                "project_id": project_id,
                "error": str(e)
            }

    async def clean(
        self,
        sql_pairs: List[SqlPair] = [],
        project_id: Optional[str] = None,
        delete_all: bool = False,
    ) -> None:
        """Clean documents for the specified SQL pairs or project."""
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
            elif sql_pairs:
                # Delete documents for specific SQL pairs
                sql_pair_ids = [sql_pair.id for sql_pair in sql_pairs]
                logger.info(f"Deleting documents for SQL pair IDs: {sql_pair_ids}")
                self._document_store.collection.delete(
                    where={"sql_pair_id": {"$in": sql_pair_ids}}
                )
                logger.info(f"Successfully deleted documents for SQL pair IDs: {sql_pair_ids}")
                
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
        collection_name="sql_pairs"
    )
    
    logger.info("Creating SQL Pairs processor")
    processor = SqlPairs(
        document_store=doc_store,
        embedder=embeddings
    )
    
    # Example MDL string
    logger.info("Processing test MDL string")
    mdl_str = '{"models": [], "views": [], "relationships": [], "metrics": []}'
    
    # Process the SQL pairs
    logger.info("Starting test processing")
    import asyncio
    result = asyncio.run(processor.run(mdl_str, project_id="test"))
    logger.info(f"Test processing completed: {result}")
