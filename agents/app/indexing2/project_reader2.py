"""
Project Reader v2 - Using Unified Storage from Indexing2

This module provides a project reader that uses the unified storage
system from indexing2 to read MDL JSONs and create ChromaDB collections.

Features:
- Unified storage using StorageManager
- Enhanced document building with business context
- Natural language search capabilities
- TF-IDF support for quick reference lookups
- Support for historical questions, SQL pairs, and instructions
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any, List

# Override ChromaDB settings to use local storage BEFORE importing ChromaDB
import os
os.environ.setdefault("CHROMA_STORE_PATH", "./chroma_db")
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8000")

import chromadb
from langchain_openai import OpenAIEmbeddings

from app.indexing2.storage_manager import StorageManager
from app.indexing2.document_builder import DocumentBuilder
from app.indexing2.ddl_chunker import DDLChunker
from app.indexing2.natural_language_search import NaturalLanguageSearch
from app.indexing2.sql_pairs import SqlPairs
from app.indexing2.historical_question import HistoricalQuestion
from app.indexing2.instructions import Instructions
from app.indexing2.instructions import Instruction
from app.indexing2.retrieval_helper2 import RetrievalHelper2
from app.indexing2.retrieval2 import TableRetrieval2
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_chromadb_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()


class ProjectReader2:
    """
    Project Reader v2 using unified storage from indexing2.
    
    This class reads MDL JSONs and creates ChromaDB collections using
    the new unified storage system with enhanced business context.
    """
    
    def __init__(
        self,
        base_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta",
        persistent_client: chromadb.PersistentClient = None,
        embeddings: OpenAIEmbeddings = None,
        use_local_storage: bool = True
    ):
        """Initialize ProjectReader2 with unified storage.
        
        Args:
            base_path: Base path to the project directory
            persistent_client: Optional ChromaDB persistent client
            embeddings: Optional embeddings model
            use_local_storage: If True, use local ChromaDB storage (default: True)
        """
        logger.info(f"Initializing ProjectReader2 with base path: {base_path}")
        self.base_path = Path(base_path)
        
        # Initialize ChromaDB client
        if persistent_client is not None:
            self.persistent_client = persistent_client
        elif use_local_storage:
            # Force local storage
            local_path = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/lexy/v2/chroma_db" #os.environ.get("CHROMA_STORE_PATH", "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/lexy/v2/chroma_db")
            logger.info(f"Using local ChromaDB storage at: {local_path}")
            self.persistent_client = chromadb.PersistentClient(path=local_path)
        else:
            # Use remote client from dependencies
            self.persistent_client = get_chromadb_client()
        
        # Get settings for embeddings
        settings = get_settings()
        self.embeddings = embeddings or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize document stores
        logger.info("Initializing document stores")
        self._init_document_stores()
        
        # Initialize components with unified storage
        logger.info("Initializing unified storage components")
        self._init_components()
        
        logger.info("ProjectReader2 initialization complete")
    
    def _init_document_stores(self):
        """Initialize document stores for unified storage."""
        logger.info("Setting up document stores")
        
        # Create unified document store
        self.unified_doc_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="unified_storage",
            embeddings_model=self.embeddings
        )
        
        # Create store for SQL pairs
        self.sql_pairs_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="sql_pairs",
            embeddings_model=self.embeddings
        )
        
        # Create store for historical questions
        self.historical_question_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="historical_question",
            embeddings_model=self.embeddings
        )
        
        # Create store for instructions
        self.instructions_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="instructions",
            embeddings_model=self.embeddings
        )
        
        logger.info("Document stores initialized successfully")
    
    def _init_components(self):
        """Initialize all indexing components with unified storage."""
        logger.info("Setting up indexing components")
        
        # Initialize storage manager with unified storage
        self.storage_manager = StorageManager(
            document_store=self.unified_doc_store,
            embedder=self.embeddings,
            column_batch_size=100,
            enable_tfidf=True
        )
        
        # Initialize document builder
        self.document_builder = DocumentBuilder()
        
        # Initialize DDL chunker
        self.ddl_chunker = DDLChunker(column_batch_size=100)
        
        # Initialize natural language search
        self.natural_language_search = NaturalLanguageSearch()
        
        # Initialize SQL pairs processor
        self.sql_pairs_processor = SqlPairs(
            document_store=self.sql_pairs_store,
            embedder=self.embeddings
        )
        
        # Initialize historical question processor
        self.historical_question_processor = HistoricalQuestion(
            document_store=self.historical_question_store,
            embedder=self.embeddings
        )
        
        # Initialize instructions processor
        self.instructions_processor = Instructions(
            document_store=self.instructions_store,
            embedder=self.embeddings
        )
        
        # Initialize retrieval helper
        self.retrieval_helper = RetrievalHelper2(
            document_store=self.unified_doc_store,
            embedder=self.embeddings,
            similarity_threshold=0.7
        )
        
        # Initialize table retrieval
        self.table_retrieval = TableRetrieval2(
            document_store=self.unified_doc_store,
            embedder=self.embeddings,
            table_retrieval_size=10,
            table_column_retrieval_size=100
        )
        
        logger.info("All components initialized successfully")
    
    async def read_project(self, project_key: str) -> Dict:
        """Read all project files and organize the data using unified storage.
        
        Args:
            project_key: The project key to read
            
        Returns:
            Dictionary containing project data and processing results
        """
        logger.info(f"Reading project: {project_key}")
        project_path = self.base_path / project_key
        
        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")
        
        # Read project metadata
        metadata = self._read_project_metadata(project_path)
        
        # Extract the actual project_id from metadata
        project_id = metadata.get("project_id")
        if not project_id:
            raise ValueError(f"Project metadata does not contain 'project_id' field for project: {project_key}")
        
        logger.info(f"Using project_id from metadata: {project_id}")
        
        # Process each table's MDL files using unified storage
        processing_results = {
            "project_id": project_id,
            "tables": [],
            "processing_results": {}
        }
        
        for table_meta in metadata.get("tables", []):
            table_result = await self._process_table_with_unified_storage(
                project_path,
                table_meta,
                project_id
            )
            processing_results["tables"].append(table_result)
        
        # Process knowledge base files (instructions)
        knowledge_base_results = await self._process_knowledge_base_files(
            project_path,
            metadata.get("knowledge_base", []),
            project_id
        )
        
        # Process example files (SQL pairs)
        example_results = await self._process_example_files(
            project_path,
            metadata.get("examples", []),
            project_id
        )
        
        # Process views as historical questions if they have question properties
        views_results = await self._process_views_as_historical_questions(
            metadata.get("views", []),
            project_id
        )
        
        processing_results["processing_results"] = {
            "knowledge_base": knowledge_base_results,
            "examples": example_results,
            "views": views_results
        }
        
        return processing_results
    
    async def _process_table_with_unified_storage(
        self,
        project_path: Path,
        table_meta: Dict,
        project_id: str
    ) -> Dict:
        """Process table MDL using unified storage system."""
        table_name = table_meta.get("name", "unknown")
        logger.info(f"Processing table: {table_name}")
        
        try:
            # Read MDL file
            mdl_path = project_path / table_meta.get("mdl_file", "")
            if not mdl_path.exists():
                logger.warning(f"MDL file not found: {mdl_path}")
                return {"name": table_name, "error": "MDL file not found"}
            
            with open(mdl_path, "r") as f:
                mdl_str = f.read()
            
            # Process MDL using unified storage
            logger.info(f"Processing MDL with unified storage for table: {table_name}")
            result = await self.storage_manager.process_mdl(
                mdl_str=mdl_str,
                project_id=project_id
            )
            
            logger.info(f"Table {table_name} processed successfully")
            return {
                "name": table_name,
                "display_name": table_meta.get("display_name", ""),
                "description": table_meta.get("description", ""),
                "processing_result": result
            }
            
        except Exception as e:
            logger.error(f"Error processing table {table_name}: {str(e)}")
            return {
                "name": table_name,
                "error": str(e)
            }
    
    async def _process_knowledge_base_files(
        self,
        project_path: Path,
        knowledge_base_metadata: List[Dict],
        project_id: str
    ) -> Dict[str, Any]:
        """Process knowledge base files (instructions)."""
        logger.info("Processing knowledge base files")
        
        all_instructions = []
        for kb_meta in knowledge_base_metadata:
            instructions_path = project_path / kb_meta.get("file_path", "")
            
            if not instructions_path.exists():
                logger.warning(f"Instructions file not found: {instructions_path}")
                continue
            
            try:
                # Read instructions file
                with open(instructions_path, "r") as f:
                    content = f.read().strip()
                
                if not content:
                    continue
                
                # Parse JSON
                instructions_data = json.loads(content)
                
                # Convert to Instruction objects
                for instruction_data in instructions_data:
                    instruction = Instruction(**instruction_data)
                    all_instructions.append(instruction)
                
            except Exception as e:
                logger.error(f"Error reading instructions file {instructions_path}: {str(e)}")
                continue
        
        # Process instructions using the processor
        if all_instructions:
            logger.info(f"Processing {len(all_instructions)} instructions")
            result = await self.instructions_processor.run(
                instructions=all_instructions,
                project_id=project_id
            )
            
            return {
                "instructions_processed": len(all_instructions),
                "result": result
            }
        
        return {"instructions_processed": 0}
    
    async def _process_example_files(
        self,
        project_path: Path,
        examples_metadata: List[Dict],
        project_id: str
    ) -> Dict[str, Any]:
        """Process example files (SQL pairs)."""
        logger.info("Processing example files")
        
        all_sql_pairs = []
        for example_meta in examples_metadata:
            sql_pairs_path = project_path / example_meta.get("file_path", "")
            
            if not sql_pairs_path.exists():
                logger.warning(f"SQL pairs file not found: {sql_pairs_path}")
                continue
            
            try:
                # Read SQL pairs file
                with open(sql_pairs_path, "r") as f:
                    content = f.read().strip()
                
                if not content:
                    continue
                
                # Parse JSON
                sql_pairs_data = json.loads(content)
                
                # Store as dictionaries (SqlPairs.run expects List[Dict[str, Any]])
                if isinstance(sql_pairs_data, dict):
                    # Handle grouped SQL pairs
                    for boilerplate, pairs in sql_pairs_data.items():
                        for pair_data in pairs:
                            sql_pair_dict = {
                                "question": pair_data.get("question", ""),
                                "sql": pair_data.get("sql", ""),
                                "instructions": pair_data.get("instructions"),
                                "chain_of_thought": pair_data.get("chain_of_thought")
                            }
                            all_sql_pairs.append(sql_pair_dict)
                elif isinstance(sql_pairs_data, list):
                    # Handle list of SQL pairs
                    for pair_data in sql_pairs_data:
                        sql_pair_dict = {
                            "question": pair_data.get("question", ""),
                            "sql": pair_data.get("sql", ""),
                            "instructions": pair_data.get("instructions"),
                            "chain_of_thought": pair_data.get("chain_of_thought")
                        }
                        all_sql_pairs.append(sql_pair_dict)
                
            except Exception as e:
                logger.error(f"Error reading SQL pairs file {sql_pairs_path}: {str(e)}")
                continue
        
        # Process SQL pairs using the processor
        if all_sql_pairs:
            logger.info(f"Processing {len(all_sql_pairs)} SQL pairs")
            result = await self.sql_pairs_processor.run(
                sql_pairs=all_sql_pairs,  # Pass as list of dictionaries
                project_id=project_id
            )
            
            return {
                "sql_pairs_processed": len(all_sql_pairs),
                "result": result
            }
        
        return {"sql_pairs_processed": 0}
    
    async def _process_views_as_historical_questions(
        self,
        views_metadata: List[Dict],
        project_id: str
    ) -> Dict[str, Any]:
        """Process views as historical questions if they have question properties."""
        logger.info("Processing views as historical questions")
        
        # Create MDL structure with views
        mdl_with_views = {
            "models": [],
            "relationships": [],
            "views": views_metadata,
            "metrics": []
        }
        
        mdl_str = json.dumps(mdl_with_views)
        
        # Process using historical question processor
        if views_metadata:
            logger.info(f"Processing {len(views_metadata)} views as historical questions")
            result = await self.historical_question_processor.run(
                mdl_str=mdl_str,
                project_id=project_id
            )
            
            return {
                "views_processed": len(views_metadata),
                "result": result
            }
        
        return {"views_processed": 0}
    
    def _read_project_metadata(self, project_path: Path) -> Dict:
        """Read project metadata file."""
        metadata_path = project_path / "project_metadata.json"
        if not metadata_path.exists():
            raise ValueError(f"Project metadata not found: {metadata_path}")
        
        with open(metadata_path, "r") as f:
            return json.load(f)
    
    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete all data associated with a project from all document stores.
        
        Args:
            project_id: The project ID to delete
            
        Returns:
            Dictionary containing deletion results
        """
        logger.info(f"Starting deletion of project: {project_id}")
        
        deletion_results = {
            "project_id": project_id,
            "components_deleted": {},
            "total_documents_deleted": 0,
            "errors": []
        }
        
        try:
            # Delete from unified storage
            try:
                logger.info("Deleting from unified storage")
                await self.storage_manager.clean(project_id=project_id)
                deletion_results["components_deleted"]["unified_storage"] = "deleted"
            except Exception as e:
                logger.error(f"Error deleting from unified storage: {str(e)}")
                deletion_results["errors"].append(f"unified_storage: {str(e)}")
            
            # Delete from SQL pairs
            try:
                logger.info("Deleting SQL pairs")
                await self.sql_pairs_processor.clean(project_id=project_id)
                deletion_results["components_deleted"]["sql_pairs"] = "deleted"
            except Exception as e:
                logger.error(f"Error deleting SQL pairs: {str(e)}")
                deletion_results["errors"].append(f"sql_pairs: {str(e)}")
            
            # Delete from historical questions
            try:
                logger.info("Deleting historical questions")
                await self.historical_question_processor.clean(project_id=project_id)
                deletion_results["components_deleted"]["historical_question"] = "deleted"
            except Exception as e:
                logger.error(f"Error deleting historical questions: {str(e)}")
                deletion_results["errors"].append(f"historical_question: {str(e)}")
            
            # Delete from instructions
            try:
                logger.info("Deleting instructions")
                await self.instructions_processor.clean(project_id=project_id)
                deletion_results["components_deleted"]["instructions"] = "deleted"
            except Exception as e:
                logger.error(f"Error deleting instructions: {str(e)}")
                deletion_results["errors"].append(f"instructions: {str(e)}")
            
            logger.info(f"Project deletion completed for {project_id}")
            return deletion_results
            
        except Exception as e:
            error_msg = f"Error during project deletion for {project_id}: {str(e)}"
            logger.error(error_msg)
            deletion_results["errors"].append(error_msg)
            return deletion_results
    
    async def query_and_retrieve_schemas(
        self,
        natural_language_question: Optional[str] = None,
        project_id: str = None,
        table_retrieval_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query and retrieve database schemas and contexts using natural language.
        
        Args:
            natural_language_question: The natural language question/query (optional, if None/empty returns all tables)
            project_id: The project ID to query
            table_retrieval_config: Optional configuration for table retrieval
            
        Returns:
            Dictionary containing retrieved schemas, contexts, and metadata
        """
        logger.info("=" * 80)
        logger.info("NATURAL LANGUAGE RETRIEVAL")
        logger.info("=" * 80)
        
        # Handle default behavior: if no query provided, use empty string to get all tables
        query = natural_language_question if natural_language_question else ""
        
        logger.info(f"Question: {query if query else '(no query - will return all tables)'}")
        logger.info(f"Project ID: {project_id}")
        
        try:
            # Use default configuration if not provided
            if table_retrieval_config is None:
                table_retrieval_config = {
                    "table_retrieval_size": 100,  # Increase limit to get all tables
                    "table_column_retrieval_size": 100,
                    "allow_using_db_schemas_without_pruning": False
                }
            
            # Test 1: Get database schemas
            logger.info("\n" + "="*80)
            logger.info("TEST 1: DATABASE SCHEMAS RETRIEVAL")
            logger.info("="*80)
            schemas_result = await self.retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval=table_retrieval_config,
                query=query,
                tables=None
            )
            
            logger.info(f"Total schemas found: {schemas_result.get('total_schemas', 0)}")
            logger.info(f"Has calculated field: {schemas_result.get('has_calculated_field', False)}")
            logger.info(f"Has metric: {schemas_result.get('has_metric', False)}")
            
            if schemas_result.get('schemas'):
                for i, schema in enumerate(schemas_result['schemas'][:5], 1):
                    logger.info(f"\nSchema {i}:")
                    logger.info(f"  Table Name: {schema.get('table_name', 'N/A')}")
                    logger.info(f"  DDL Length: {len(schema.get('table_ddl', ''))}")
                    logger.info(f"  Column Metadata Count: {len(schema.get('column_metadata', []))}")
                    logger.info(f"  Relationships Count: {len(schema.get('relationships', []))}")
                    logger.info(f"  Relevance Score: {schema.get('relevance_score', 0.0):.4f}")
                    if schema.get('table_ddl'):
                        ddl_preview = schema['table_ddl']
                        logger.info(f"  DDL Preview: {ddl_preview}...")
            
            # Test 2: Get table names and schema contexts
            logger.info("\n" + "="*80)
            logger.info("TEST 2: TABLE NAMES AND SCHEMA CONTEXTS")
            logger.info("="*80)
            table_contexts_result = await self.retrieval_helper.get_table_names_and_schema_contexts(
                query=query,
                project_id=project_id,
                table_retrieval=table_retrieval_config,
                tables=None
            )
            
            logger.info(f"Total tables: {table_contexts_result.get('total_tables', 0)}")
            logger.info(f"Total contexts: {table_contexts_result.get('total_contexts', 0)}")
            logger.info(f"Total relationships: {table_contexts_result.get('total_relationships', 0)}")
            
            if table_contexts_result.get('table_names'):
                logger.info("Table names:")
                for table_name in table_contexts_result['table_names']:
                    logger.info(f"  - {table_name}")
            
            # Test 3: Get SQL pairs
            logger.info("\n" + "="*80)
            logger.info("TEST 3: SQL PAIRS RETRIEVAL")
            logger.info("="*80)
            sql_pairs_result = await self.retrieval_helper.get_sql_pairs(
                query=query,
                project_id=project_id,
                max_retrieval_size=5
            )
            
            logger.info(f"Total SQL pairs found: {sql_pairs_result.get('total_pairs', 0)}")
            
            if sql_pairs_result.get('sql_pairs'):
                for i, pair in enumerate(sql_pairs_result['sql_pairs'][:3], 1):
                    logger.info(f"\nSQL Pair {i}:")
                    logger.info(f"  Question: {pair.get('question', 'N/A')}")
                    logger.info(f"  SQL Preview: {pair.get('sql', 'N/A')[:100]}...")
                    logger.info(f"  Score: {pair.get('score', 0.0):.4f}")
            
            # Test 4: Get instructions
            logger.info("\n" + "="*80)
            logger.info("TEST 4: INSTRUCTIONS RETRIEVAL")
            logger.info("="*80)
            instructions_result = await self.retrieval_helper.get_instructions(
                query=query,
                project_id=project_id,
                top_k=5
            )
            
            logger.info(f"Total instructions found: {instructions_result.get('total_instructions', 0)}")
            
            if instructions_result.get('instructions'):
                for i, inst in enumerate(instructions_result['instructions'][:3], 1):
                    logger.info(f"\nInstruction {i}:")
                    logger.info(f"  Question: {inst.get('question', 'N/A')}")
                    logger.info(f"  Instruction: {inst.get('instruction', 'N/A')[:100]}...")
            
            # Test 5: Get historical questions
            logger.info("\n" + "="*80)
            logger.info("TEST 5: HISTORICAL QUESTIONS RETRIEVAL")
            logger.info("="*80)
            historical_result = await self.retrieval_helper.get_historical_questions(
                query=query,
                project_id=project_id
            )
            
            logger.info(f"Total historical questions found: {historical_result.get('total_questions', 0)}")
            
            if historical_result.get('historical_questions'):
                for i, hist in enumerate(historical_result['historical_questions'][:3], 1):
                    logger.info(f"\nHistorical Question {i}:")
                    logger.info(f"  Question: {hist.get('question', 'N/A')}")
                    logger.info(f"  Summary: {hist.get('summary', 'N/A')[:100]}...")
            
            # Compile results
            retrieval_summary = {
                "query": query,
                "project_id": project_id,
                "schemas": {
                    "total_schemas": schemas_result.get('total_schemas', 0),
                    "has_calculated_field": schemas_result.get('has_calculated_field', False),
                    "has_metric": schemas_result.get('has_metric', False)
                },
                "table_contexts": {
                    "total_tables": table_contexts_result.get('total_tables', 0),
                    "total_contexts": table_contexts_result.get('total_contexts', 0),
                    "total_relationships": table_contexts_result.get('total_relationships', 0),
                    "table_names": table_contexts_result.get('table_names', [])
                },
                "sql_pairs": {
                    "total_pairs": sql_pairs_result.get('total_pairs', 0)
                },
                "instructions": {
                    "total_instructions": instructions_result.get('total_instructions', 0)
                },
                "historical_questions": {
                    "total_questions": historical_result.get('total_questions', 0)
                }
            }
            
            logger.info("\n" + "="*80)
            logger.info("RETRIEVAL SUMMARY")
            logger.info("="*80)
            logger.info(f"Schemas Found: {retrieval_summary['schemas']['total_schemas']}")
            logger.info(f"Tables Found: {retrieval_summary['table_contexts']['total_tables']}")
            logger.info(f"SQL Pairs Found: {retrieval_summary['sql_pairs']['total_pairs']}")
            logger.info(f"Instructions Found: {retrieval_summary['instructions']['total_instructions']}")
            logger.info(f"Historical Questions Found: {retrieval_summary['historical_questions']['total_questions']}")
            logger.info("="*80)
            
            return retrieval_summary
            
        except Exception as e:
            logger.error(f"Error in natural language retrieval: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "query": query,
                "project_id": project_id,
                "error": str(e)
            }


async def main():
    """Main function to test ProjectReader2."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set up base path
    base_path = Path("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta")
    
    # Initialize reader with local storage by default
    logger.info("Initializing ProjectReader2 with LOCAL storage")
    reader = ProjectReader2(
        base_path=base_path,
        persistent_client=None,  # Will use local storage
        embeddings=None,  # Will use default embeddings
        use_local_storage=True  # Force local storage
    )
    
    # Test projects
    test_projects = ["sumtotal_learn"]  # Add more projects as needed
    
    for project in test_projects:
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing project: {project}")
            logger.info(f"{'='*50}")
            
            # Read project
            project_data = await reader.read_project(project)
            
            # Print summary
            logger.info(f"\nProject ID: {project_data['project_id']}")
            
            # Print tables summary
            logger.info("\nTables:")
            for table in project_data['tables']:
                logger.info(f"- {table.get('name', 'unknown')}")
                logger.info(f"  Display Name: {table.get('display_name', 'N/A')}")
                logger.info(f"  Description: {table.get('description', 'N/A')}")
                
                # Print processing results
                if 'processing_result' in table:
                    result = table['processing_result']
                    logger.info(f"  Documents Written: {result.get('documents_written', 0)}")
                    logger.info(f"  Unified Documents: {result.get('unified_documents', 0)}")
                    logger.info(f"  Individual Documents: {result.get('individual_documents', 0)}")
                    logger.info(f"  Table Documents: {result.get('table_documents', 0)}")
                    logger.info(f"  Table Column Documents: {result.get('table_column_documents', 0)}")
            
            # Print knowledge base summary
            logger.info("\nKnowledge Base Processing:")
            kb_results = project_data['processing_results'].get('knowledge_base', {})
            logger.info(f"  Instructions Processed: {kb_results.get('instructions_processed', 0)}")
            
            # Print examples summary
            logger.info("\nExamples Processing:")
            examples_results = project_data['processing_results'].get('examples', {})
            logger.info(f"  SQL Pairs Processed: {examples_results.get('sql_pairs_processed', 0)}")
            
            # Print views summary
            logger.info("\nViews Processing:")
            views_results = project_data['processing_results'].get('views', {})
            logger.info(f"  Views Processed: {views_results.get('views_processed', 0)}")
            
            # First, verify that documents exist in the storage
            logger.info("\n" + "="*80)
            logger.info("VERIFYING DOCUMENTS IN STORAGE")
            logger.info("="*80)
            
            # Try to get document count and sample documents
            try:
                doc_count = reader.unified_doc_store.collection.count()
                logger.info(f"Documents in unified_storage collection: {doc_count}")
                
                # Get a sample of documents to see what's stored
                if doc_count > 0:
                    sample_results = reader.unified_doc_store.collection.get(
                        limit=5
                    )
                    logger.info(f"\nSample documents (showing {len(sample_results.get('ids', []))} documents):")
                    for i, (doc_id, metadata_dict) in enumerate(zip(
                        sample_results.get('ids', []),
                        sample_results.get('metadatas', [])
                    ), 1):
                        logger.info(f"\n  Document {i}:")
                        logger.info(f"    ID: {doc_id}")
                        logger.info(f"    Metadata: {metadata_dict}")
                        
                        # Try to get the document content
                        try:
                            doc_result = reader.unified_doc_store.collection.get(
                                ids=[doc_id]
                            )
                            if doc_result.get('documents'):
                                content_preview = doc_result['documents'][0][:200] if doc_result['documents'] else ""
                                logger.info(f"    Content preview: {content_preview}...")
                        except Exception as e:
                            logger.warning(f"    Could not get content: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not get document information: {str(e)}")
                import traceback
                logger.warning(f"Traceback: {traceback.format_exc()}")
            
            # Test with default behavior (no query) - should return all tables
            logger.info("\n" + "="*80)
            logger.info("TESTING DEFAULT RETRIEVAL (ALL TABLES)")
            logger.info("="*80)
            
            retrieval_result_all = await reader.query_and_retrieve_schemas(
                natural_language_question=None,  # No query - should return all tables
                project_id=project_data['project_id']
            )
            
            logger.info("\nAll tables retrieval test completed successfully!")
            
            # Test with a simpler query first to verify retrieval works
            logger.info("\n" + "="*80)
            logger.info("TESTING NATURAL LANGUAGE RETRIEVAL WITH SIMPLE QUERY")
            logger.info("="*80)
            
            test_question = "user training"
            logger.info(f"Testing with simple query: '{test_question}'")
            
            retrieval_result = await reader.query_and_retrieve_schemas(
                natural_language_question=test_question,
                project_id=project_data['project_id']
            )
            
            logger.info("\nRetrieval test completed successfully!")
            
            # Now test with the original complex question
            logger.info("\n" + "="*80)
            logger.info("TESTING NATURAL LANGUAGE RETRIEVAL WITH COMPLEX QUERY")
            logger.info("="*80)
            
            complex_question = "What is the completion status of the onboarding curriculum for my new hires (joined in the last 90 days)? "
            retrieval_result2 = await reader.query_and_retrieve_schemas(
                natural_language_question=complex_question,
                project_id=project_data['project_id']
            )
            
            logger.info("\nComplex retrieval test completed successfully!")
            
        except Exception as e:
            logger.error(f"Error processing project {project}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

