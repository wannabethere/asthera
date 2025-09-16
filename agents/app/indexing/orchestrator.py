import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any

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
class IndexingOrchestrator:
    """Orchestrates the indexing process for all components."""
    
    def __init__(self, base_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta", persistent_client: chromadb.PersistentClient = None, embeddings: OpenAIEmbeddings = None):
        logger.info(f"Initializing IndexingOrchestrator with base path: {base_path}")
        self.base_path = Path(base_path)
        self.persistent_client = persistent_client
        self.embeddings = embeddings
        
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

    async def process_project(self, project_key: str) -> Dict[str, Any]:
        """Process a project's metadata and create indexes."""
        logger.info(f"Starting project processing for: {project_key}")
        project_path = self.base_path / project_key
        
        if not project_path.exists():
            error_msg = f"Project path does not exist: {project_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Load MDL file
        mdl_path = project_path / "mdl.json"
        if not mdl_path.exists():
            error_msg = f"MDL file not found: {mdl_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info(f"Loading MDL file from: {mdl_path}")
        with open(mdl_path, "r") as f:
            mdl_str = f.read()
        
                    
        # Load instructions if they exist
        instructions = []
        instructions_path = project_path / "instructions.json"
        if instructions_path.exists():
            logger.info(f"Loading instructions from: {instructions_path}")
            try:
                # Check if file is empty
                if instructions_path.stat().st_size == 0:
                    logger.warning(f"Instructions file is empty: {instructions_path}")
                else:
                    with open(instructions_path, "r") as f:
                        content = f.read().strip()
                        
                    if not content:
                        logger.warning(f"Instructions file contains only whitespace: {instructions_path}")
                    else:
                        try:
                            instructions_data = json.loads(content)
                            if isinstance(instructions_data, list) and len(instructions_data) > 0:
                                instructions = [
                                    Instruction(**instruction)
                                    for instruction in instructions_data
                                ]
                                logger.info(f"Loaded {len(instructions)} instructions")
                            else:
                                logger.warning(f"Instructions file contains invalid data structure: {instructions_path}")
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON in instructions file {instructions_path}: {str(e)}")
            except Exception as e:
                logger.error(f"Error loading instructions file {instructions_path}: {str(e)}")
        else:
            logger.warning(f"Instructions file not found: {instructions_path}")
            
        # Load SQL pairs if they exist
        sql_pairs = []
        sql_pairs_path = project_path / "sql_pairs.json"
        if sql_pairs_path.exists():
            logger.info(f"Loading SQL pairs from: {sql_pairs_path}")
            try:
                # Check if file is empty
                if sql_pairs_path.stat().st_size == 0:
                    logger.warning(f"SQL pairs file is empty: {sql_pairs_path}")
                else:
                    with open(sql_pairs_path, "r") as f:
                        content = f.read().strip()
                        
                    if not content:
                        logger.warning(f"SQL pairs file contains only whitespace: {sql_pairs_path}")
                    else:
                        try:
                            sql_pairs = json.loads(content)
                            if isinstance(sql_pairs, list) and len(sql_pairs) > 0:
                                logger.info(f"Loaded {len(sql_pairs)} SQL pairs")
                            else:
                                logger.warning(f"SQL pairs file contains invalid data structure: {sql_pairs_path}")
                                sql_pairs = []
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON in SQL pairs file {sql_pairs_path}: {str(e)}")
                            sql_pairs = []
            except Exception as e:
                logger.error(f"Error loading SQL pairs file {sql_pairs_path}: {str(e)}")
                sql_pairs = []
        else:
            logger.warning(f"SQL pairs file not found: {sql_pairs_path}")
        
        # Process each component
        results = {}
        
        try:
            
            # Process DB Schema with MDL
            project_id= "LEXY_HR"
            
            logger.info("Processing DB Schema with MDL")
            results["db_schema"] = await self.components["db_schema"].run(
                mdl_str=mdl_str,
                project_id=project_id
            )
            logger.info(f"DB Schema processing complete: {results['db_schema']}")
            
            
            # Process Table Descriptions with MDL
            logger.info(f"Processing Table Descriptions with MDL {project_key}")
            results["table_description"] = await self.components["table_description"].run(
                mdl=mdl_str,
                project_id=project_id
            )
            logger.info(f"Table Descriptions processing complete: {results['table_description']}")
            
            
            # Process Historical Questions with MDL
            logger.info("Processing Historical Questions with MDL")
            results["historical_question"] = await self.components["historical_question"].run(
                mdl_str=mdl_str,
                project_id=project_id
            )
            logger.info(f"Historical Questions processing complete: {results['historical_question']}")
            
            # Process Instructions with instructions.json
            
            if instructions:
                logger.info("Processing Instructions from instructions.json")
                results["instructions"] = await self.components["instructions"].run(
                    instructions=instructions,
                    project_id=project_id
                )
                logger.info(f"Instructions processing complete: {results['instructions']}")
            else:
                logger.info("Skipping Instructions processing - no instructions found")
            
          

            # Process Project Meta with MDL
            logger.info("Processing Project Meta with MDL")
            results["project_meta"] = await self.components["project_meta"].run(
                mdl_str=mdl_str,
                project_id=project_id
            )
            logger.info(f"Project Meta processing complete: {results['project_meta']}")
            
            # Process SQL Pairs with sql_pairs.json
            if sql_pairs:
                logger.info("Processing SQL Pairs from sql_pairs.json")
                results["sql_pairs"] = await self.components["sql_pairs"].run(
                    sql_pairs=sql_pairs,
                    project_id=project_id
                )
                logger.info(f"SQL Pairs processing complete: {results['sql_pairs']}")
            else:
                logger.info("Skipping SQL Pairs processing - no SQL pairs found")
            
            logger.info(f"Successfully completed all processing for project: {project_key}")
            
            return results
            
        except Exception as e:
            error_msg = f"Error processing project {project_key}: {str(e)}"
            logger.error(error_msg)
            raise

    async def clean_project(self, project_key: str) -> Dict[str, Any]:
        """Clean all indexes for a project.
        
        Args:
            project_key: The project key/ID to clean
            
        Returns:
            Dictionary containing cleanup results for each component
        """
        logger.info(f"Starting cleanup for project: {project_key}")
        
        cleanup_results = {
            "project_id": project_key,
            "components_cleaned": {},
            "total_documents_deleted": 0,
            "errors": []
        }
        
        for component_name, component in self.components.items():
            try:
                logger.info(f"Cleaning {component_name} for project: {project_key}")
                await component.clean(project_id=project_key)
                cleanup_results["components_cleaned"][component_name] = "success"
                logger.info(f"Successfully cleaned {component_name}")
            except Exception as e:
                error_msg = f"Error cleaning {component_name}: {str(e)}"
                logger.error(error_msg)
                cleanup_results["errors"].append(error_msg)
                cleanup_results["components_cleaned"][component_name] = f"error: {str(e)}"
        
        logger.info(f"Cleanup completed for project: {project_key}")
        return cleanup_results

if __name__ == "__main__":
    import asyncio
    
    # Initialize the orchestrator
    logger.info("Initializing embeddings and ChromaDB client")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    persistent_client = chromadb.PersistentClient(
        path=settings.CHROMA_STORE_PATH
    )
    
    logger.info("Creating IndexingOrchestrator instance")
    orchestrator = IndexingOrchestrator(persistent_client=persistent_client, embeddings=embeddings)
    
    # Process projects
    async def main():
        try:
            # Process corner_stone project
            logger.info("Starting processing for corner_stone project")
            results = await orchestrator.process_project("cornerstone")
            logger.info(f"Corner stone processing results: {results}")
            
            # Process employee_training project
            logger.info("Starting processing for employee_training project")
            results = await orchestrator.process_project("employee_training")
            logger.info(f"Employee training processing results: {results}")
            
        except Exception as e:
            logger.error(f"Error in main process: {str(e)}")
            raise
            
    logger.info("Starting main process")
    asyncio.run(main())
    logger.info("Main process completed") 