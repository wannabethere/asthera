import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any, List

import chromadb
from langchain_openai import OpenAIEmbeddings

from app.indexing.db_schema import DBSchema
from app.indexing.table_description import TableDescription
from app.indexing.historical_question import HistoricalQuestion
from app.indexing.instructions import Instructions, Instruction
from app.indexing.project_meta import ProjectMeta
from app.indexing.sql_pairs import SqlPairs
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_doc_store_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()

class ProjectReader:
    def __init__(self, base_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta", persistent_client: chromadb.PersistentClient = None, embeddings: OpenAIEmbeddings = None):
        logger.info(f"Initializing IndexingOrchestrator with base path: {base_path}")
        self.base_path = Path(base_path)
        print(f"Initializing IndexingOrchestrator with base path: {base_path}")

        self.persistent_client = persistent_client#chromadb.HttpClient(host='ec2-54-161-71-105.compute-1.amazonaws.com', port=8888)
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        
        # Initialize document stores for each component
        logger.info("Initializing document stores")
        self._init_document_stores()
        
        # Initialize indexing components
        logger.info("Initializing indexing components")
        self._init_components()
        logger.info("IndexingOrchestrator initialization complete")

    def _init_document_stores(self):
        """Initialize document stores for each component."""
        logger.info("Setting up document stores for each component")
        self.document_stores = get_doc_store_provider().stores
        logger.info("Document stores initialized successfully")

    def _init_components(self):
        """Initialize all indexing components."""
        logger.info("Setting up indexing components")
        self.components = {
            "db_schema": DBSchema(
                document_store=self.document_stores["db_schema"],
                embedder=self.embeddings
            ),
            "table_description": TableDescription(
                document_store=self.document_stores["table_description"],
                embedder=self.embeddings
            ),
            "historical_question": HistoricalQuestion(
                document_store=self.document_stores["historical_question"],
                embedder=self.embeddings
            ),
            "instructions": Instructions(
                document_store=self.document_stores["instructions"],
                embedder=self.embeddings
            ),
            "project_meta": ProjectMeta(
                document_store=self.document_stores["project_meta"]
            ),
            "sql_pairs": SqlPairs(
                document_store=self.document_stores["sql_pairs"],
                embedder=self.embeddings
            )
        }
        logger.info("All components initialized successfully")

    async def read_project(self, project_key: str) -> Dict:
        """Read all project files and organize the data."""
        logger.info(f"Reading project: {project_key}")
        project_path = self.base_path / project_key
        
        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        # Read project metadata
        metadata = self._read_project_metadata(project_path)
        
        # Process each table's files
        tables = []
        for table_meta in metadata["tables"]:
            table_data = await self._process_table_files(project_path, table_meta, metadata["project_id"])
            tables.append(table_data)
        
        # Process knowledge base files
        knowledge_base = await self._process_knowledge_base_files(project_path, metadata.get("knowledge_base", []), metadata["project_id"])
        
        # Process example files
        examples = await self._process_example_files(project_path, metadata.get("examples", []), metadata["project_id"])

        return {
            "project_id": metadata["project_id"],
            "tables": tables,
            "knowledge_base": knowledge_base,
            "examples": examples
        }

    def _read_project_metadata(self, project_path: Path) -> Dict:
        """Read project metadata file."""
        metadata_path = project_path / "project_metadata.json"
        if not metadata_path.exists():
            raise ValueError(f"Project metadata not found: {metadata_path}")
        
        with open(metadata_path, "r") as f:
            return json.load(f)

    async def _process_table_files(self, project_path: Path, table_meta: Dict, project_id: str) -> Dict:
        """Process MDL and DDL files for a table."""
        table_data = {
            "name": table_meta["name"],
            "display_name": table_meta["display_name"],
            "description": table_meta["description"]
        }
        
        # Process MDL file
        mdl_data = await self._process_mdl_file(project_path, table_meta["mdl_file"], project_id)
        if mdl_data:
            table_data["mdl"] = mdl_data
        
        """
        # Process DDL file if it exists
        ddl_data = self._process_ddl_file(project_path, table_meta["ddl_file"])
        if ddl_data:
            table_data["ddl"] = ddl_data
        """
        return table_data

    async def _process_mdl_file(self, project_path: Path, mdl_file: str, project_id: str) -> Optional[Dict]:
        """Process MDL file using DbSchema."""
        mdl_path = project_path / mdl_file
        if not mdl_path.exists():
            logger.warning(f"MDL file not found: {mdl_path}")
            return None
            
        logger.info(f"Processing MDL file: {mdl_path}")
        with open(mdl_path, "r") as f:
            mdl_str = f.read()
            
        try:
            # Use DbSchema to process the MDL file
            results = await self.components["db_schema"].run(
                mdl_str=mdl_str,
                project_id=project_id
            )
            
            logger.info(f"Processing Table Descriptions with MDL {project_id}")
            results["table_description"] = await self.components["table_description"].run(
                mdl=mdl_str,
                project_id=project_id
            )
            logger.info(f"Table Descriptions processing complete: {results['table_description']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing MDL file {mdl_path}: {str(e)}")
            return None

    def _process_ddl_file(self, project_path: Path, ddl_file: str) -> Optional[Dict]:
        """Process DDL file and extract relevant information."""
        ddl_path = project_path / ddl_file
        if not ddl_path.exists():
            logger.warning(f"DDL file not found: {ddl_path}")
            return None
            
        logger.info(f"Processing DDL file: {ddl_path}")
        with open(ddl_path, "r") as f:
            ddl_data = json.load(f)
            
        # Extract relevant DDL information
        processed_ddl = {
            "tables": ddl_data.get("tables", []),
            "views": ddl_data.get("views", []),
            "functions": ddl_data.get("functions", [])
        }
        
        return processed_ddl

    async def _process_knowledge_base_files(self, project_path: Path, knowledge_base_metadata: List[Dict], project_id: str) -> List[Dict]:
        """Process knowledge base files."""
        knowledge_base = []
        for kb_meta in knowledge_base_metadata:
            kb_data = await self._process_instructions_file(project_path, kb_meta["file_path"], project_id)
            if kb_data:
                knowledge_base.append({
                    "name": kb_meta["name"],
                    "display_name": kb_meta["display_name"],
                    "description": kb_meta["description"],
                    "content": kb_data
                })
        return knowledge_base

    async def _process_instructions_file(self, project_path: Path, file_path: str, project_id: str) -> Optional[Dict]:
        """Process instructions file and extract relevant information."""
        instructions_path = project_path / file_path
        if not instructions_path.exists():
            logger.warning(f"Instructions file not found: {instructions_path}")
            return None
            
        logger.info(f"Processing instructions file: {instructions_path}")
        with open(instructions_path, "r") as f:
            instructions_data = json.load(f)
            instructions = [
                Instruction(**instruction)
                for instruction in instructions_data
            ]
        logger.info(f"Loaded {len(instructions)} instructions")
            
        try:
            # Process instructions using the Instructions component
            results = await self.components["instructions"].run(
                instructions=instructions,
                project_id=project_id
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing instructions file {instructions_path}: {str(e)}")
            return None

    async def _process_example_files(self, project_path: Path, examples_metadata: List[Dict], project_id: str) -> List[Dict]:
        """Process example files."""
        examples = []
        for example_meta in examples_metadata:
            example_data = await self._process_sql_pairs_file(project_path, example_meta["file_path"], project_id)
            if example_data:
                examples.append({
                    "name": example_meta["name"],
                    "display_name": example_meta["display_name"],
                    "description": example_meta["description"],
                    "content": example_data
                })
        return examples

    async def _process_sql_pairs_file(self, project_path: Path, file_path: str, project_id: str) -> Optional[Dict]:
        """Process SQL pairs file and extract relevant information."""
        sql_pairs_path = project_path / file_path
        if not sql_pairs_path.exists():
            logger.warning(f"SQL pairs file not found: {sql_pairs_path}")
            return None
            
        logger.info(f"Processing SQL pairs file: {sql_pairs_path}")
        with open(sql_pairs_path, "r") as f:
            sql_pairs_data = json.load(f)
            
        try:
            # Process SQL pairs using the SqlPairs component
            results_str = await self.components["sql_pairs"].run(
                sql_pairs=sql_pairs_data,
                project_id=project_id
            )
            
            # Parse the JSON string response back into a dictionary
            if isinstance(results_str, str):
                results = json.loads(results_str)
            else:
                results = results_str
                
            return results
            
        except Exception as e:
            logger.error(f"Error processing SQL pairs file {sql_pairs_path}: {str(e)}")
            return None

async def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    persistent_client = chromadb.PersistentClient(
        path=settings.CHROMA_STORE_PATH
    )
    # Set up base path
    base_path = Path("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta")
    
    # Initialize reader
    reader = ProjectReader(base_path, persistent_client)
    
    # Test projects
    test_projects = ["csodworkday"]
    
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
                logger.info(f"- {table['name']} ({table['display_name']})")
                logger.info(f"  Description: {table['description']}")
                logger.info(f"  Has MDL: {'mdl' in table}")
                logger.info(f"  Has DDL: {'ddl' in table}")
                
                # Print MDL details if available
                if 'mdl' in table:
                    mdl = table['mdl']
                    logger.info(f"  MDL Catalog: {mdl.get('catalog')}")
                    logger.info(f"  MDL Schema: {mdl.get('schema')}")
                    logger.info(f"  MDL Models: {len(mdl.get('models', []))}")
                    logger.info(f"  MDL Enums: {len(mdl.get('enums', []))}")
                    logger.info(f"  MDL Metrics: {len(mdl.get('metrics', []))}")
                    logger.info(f"  MDL Views: {len(mdl.get('views', []))}")
                
                # Print DDL details if available
                if 'ddl' in table:
                    ddl = table['ddl']
                    logger.info(f"  DDL Tables: {len(ddl.get('tables', []))}")
                    logger.info(f"  DDL Views: {len(ddl.get('views', []))}")
                    logger.info(f"  DDL Functions: {len(ddl.get('functions', []))}")
            
            # Print knowledge base summary
            logger.info("\nKnowledge Base:")
            for kb in project_data['knowledge_base']:
                logger.info(f"- {kb['name']} ({kb['display_name']})")
                logger.info(f"  Description: {kb['description']}")
                if 'content' in kb:
                    content = kb['content']
                    logger.info(f"  Knowledge Base Items: {len(content.get('knowledge_base', []))}")
                    logger.info(f"  Examples: {len(content.get('examples', []))}")
                    logger.info(f"  Tags: {len(content.get('tags', []))}")
            
            # Print examples summary
            logger.info("\nExamples:")
            for example in project_data['examples']:
                logger.info(f"- {example['name']} ({example['display_name']})")
                logger.info(f"  Description: {example['description']}")
                if 'content' in example:
                    content = example['content']
                    logger.info(f"  SQL Pairs: {len(content.get('pairs', []))}")
                    logger.info(f"  Metadata Fields: {len(content.get('metadata', {}))}")
            
        except Exception as e:
            logger.error(f"Error processing project {project}: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 