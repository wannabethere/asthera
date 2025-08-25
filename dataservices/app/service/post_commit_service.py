# """
# Post-Commit Service
# Executes custom code and workflows when a domain is committed
# """

# import asyncio
# import logging
# from typing import Dict, Any, List, Optional
# from datetime import datetime
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, func
# from app.schemas.dbmodels import Domain, Dataset, Table, SQLColumn
# from sqlalchemy.orm import selectinload
# from app.service.models import DomainContext
# from app.utils.sse import publish_update
# from app.core.session_manager import SessionManager
# from app.utils.history import DomainManager
# from app.service.project_json_service import DomainJSONService

# logger = logging.getLogger(__name__)

# class PostCommitService:
#     """Service for executing post-commit operations"""
    
#     def __init__(self, user_id: str, session_id: str):
#         self.user_id = user_id
#         self.session_id = session_id
    
#     async def execute_post_commit_workflows(self, domain_id: str, db: AsyncSession) -> Dict[str, Any]:
#         """
#         Execute post-commit workflows for ChromaDB integration via LLM definition generation
#         and domain JSON schemas processing
        
#         Args:
#             domain_id: ID of the committed domain
#             db: Database session
            
#         Returns:
#             Dictionary containing execution results
#         """
#         logger.info(f"Executing post-commit ChromaDB integration for domain {domain_id}")
        
#         results = {
#             "domain_id": domain_id,
#             "executed_at": datetime.now().isoformat(),
#             "workflows": {},
#             "status": "completed",
#             "errors": [],
#             "submitted_jobs": []
#         }
        
#         try:
#             # Get domain details
#             domain = await self._get_domain_with_details(domain_id, db)
#             if not domain:
#                 raise ValueError(f"Domain {domain_id} not found")
            
#             # Execute immediate workflows
#             workflows = [
#                 ("chromadb_integration", self._setup_chromadb_integration),
#                 ("domain_json_schemas", self._process_domain_json_schemas)
#             ]
            
#             for workflow_name, workflow_func in workflows:
#                 try:
#                     logger.info(f"Executing workflow: {workflow_name}")
#                     workflow_result = await workflow_func(domain, db)
#                     results["workflows"][workflow_name] = workflow_result
#                     logger.info(f"Completed workflow: {workflow_name}")
#                 except Exception as e:
#                     error_msg = f"Error in workflow {workflow_name}: {str(e)}"
#                     logger.error(error_msg)
#                     results["errors"].append(error_msg)
#                     results["workflows"][workflow_name] = {"status": "failed", "error": str(e)}
            
#             # Note: ChromaDB indexing job is automatically submitted by entity update service
#             # when domain is committed, so we don't need to submit it here
#             logger.info(f"ChromaDB indexing job will be submitted by entity update service for domain {domain_id}")
            
#             # Publish completion update
#             publish_update(self.user_id, self.session_id, {
#                 "type": "post_commit_completed",
#                 "domain_id": domain_id,
#                 "results": results
#             })
            
#             logger.info(f"Post-commit ChromaDB integration completed for domain {domain_id}")
            
#         except Exception as e:
#             error_msg = f"Error executing post-commit ChromaDB integration: {str(e)}"
#             logger.error(error_msg)
#             results["status"] = "failed"
#             results["errors"].append(error_msg)
            
#             # Publish error update
#             publish_update(self.user_id, self.session_id, {
#                 "type": "post_commit_failed",
#                 "domain_id": domain_id,
#                 "error": str(e)
#             })
        
#         return results
    
#     async def _get_domain_with_details(self, domain_id: str, db: AsyncSession) -> Optional[Domain]:
#         """Get domain with all related details"""
#         result = await db.execute(
#             select(Domain)
#             .options(
#                 selectinload(Domain.datasets)
#                 .selectinload(Dataset.tables)
#                 .selectinload(Table.columns)
#             )
#             .where(Domain.domain_id == domain_id)
#         )
#         return result.scalar_one_or_none()
    
#     async def _setup_chromadb_integration(self, domain: Domain, db: AsyncSession) -> Dict[str, Any]:
#         """Generate LLM definitions and store in temporary MDL JSON file"""
#         logger.info(f"Generating LLM definitions for domain {domain.domain_id}")
        
#         results = {
#             "mdl_file_created": False,
#             "definitions_generated": 0,
#             "tables_processed": 0,
#             "errors": []
#         }
        
#         try:
#             # Get LLM definition generation service
#             from app.agents.schema_manager import LLMSchemaDocumentationGenerator
#             from app.core.dependencies import get_llm
            
#             llm = get_llm()
#             definition_service = LLMSchemaDocumentationGenerator(llm)
            
#             # Prepare domain context for LLM definition generation
#             domain_context = DomainContext(
#                 domain_id=domain.domain_id,
#                 domain_name=domain.display_name,
#                 business_domain=domain.json_metadata.get("context", {}).get("business_domain", "General"),
#                 purpose=domain.description or "Data domain",
#                 target_users=domain.json_metadata.get("context", {}).get("target_users", ["Data Analysts"]),
#                 key_business_concepts=domain.json_metadata.get("context", {}).get("key_business_concepts", [])
#             )
            
#             # Collect all table definitions
#             table_definitions = []
            
#             # Process each table for LLM definition generation
#             for dataset in domain.datasets:
#                 for table in dataset.tables:
#                     try:
#                         logger.info(f"Generating LLM definitions for table {table.name}")
                        
#                         # Generate LLM definitions
#                         table_result = await self._generate_table_definitions(table, domain, definition_service, domain_context)
                        
#                         if table_result["success"]:
#                             table_definitions.append(table_result["definition"])
#                             results["definitions_generated"] += 1
                        
#                         results["tables_processed"] += 1
                        
#                     except Exception as e:
#                         error_msg = f"Error generating definitions for table {table.name}: {str(e)}"
#                         logger.error(error_msg)
#                         results["errors"].append(error_msg)
            
#             # Create MDL file using MDL Builder Service for ChromaDB indexing
#             if table_definitions:
#                 try:
#                     from app.services.mdl_builder_service import mdl_builder_service
#                     from pathlib import Path
                    
#                     # Create MDL directory if it doesn't exist
#                     mdl_dir = Path("mdl_files")
#                     mdl_dir.mkdir(exist_ok=True)
                    
#                     # Create domain-specific directory
#                     domain_mdl_dir = mdl_dir / domain.domain_id
#                     domain_mdl_dir.mkdir(exist_ok=True)
                    
#                     # Create MDL file
#                     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#                     mdl_filename = f"{domain.domain_id}_definitions_{timestamp}.json"
#                     mdl_file_path = domain_mdl_dir / mdl_filename
                    
#                     # Build complete MDL using the MDL Builder Service
#                     mdl_content = await mdl_builder_service.build_domain_mdl(
#                         domain_id=domain.domain_id,
#                         db=db,
#                         include_llm_definitions=True
#                     )
                    
#                     # Save MDL to file
#                     save_result = await mdl_builder_service.save_mdl_to_file(
#                         mdl_data=mdl_content,
#                         file_path=str(mdl_file_path)
#                     )
                    
#                     if save_result["success"]:
#                         results["mdl_file_created"] = True
#                         results["mdl_file_path"] = str(mdl_file_path)
                        
#                         # Update domain metadata
#                         domain.json_metadata = domain.json_metadata or {}
#                         domain.json_metadata["llm_definitions"] = {
#                             "generated_at": datetime.now().isoformat(),
#                             "mdl_file_path": str(mdl_file_path),
#                             "definitions_count": results["definitions_generated"],
#                             "tables_processed": results["tables_processed"],
#                             "status": "pending_indexing"  # Will be updated by async job
#                         }
                        
#                         await db.commit()
#                         logger.info(f"LLM definitions and MDL file created for domain {domain.domain_id}, indexing queued")
#                     else:
#                         logger.error(f"Error saving MDL file: {save_result['error']}")
#                         results["errors"].append(f"Error saving MDL file: {save_result['error']}")
                        
#                 except Exception as e:
#                     error_msg = f"Error creating MDL file: {str(e)}"
#                     logger.error(error_msg)
#                     results["errors"].append(error_msg)
            
#         except Exception as e:
#             error_msg = f"Error in LLM definition generation: {str(e)}"
#             logger.error(error_msg)
#             results["errors"].append(error_msg)
        
#         return results
    
#     async def _generate_table_definitions(self, table: Table, domain: Domain, definition_service, domain_context: DomainContext) -> Dict[str, Any]:
#         """Generate LLM definitions for a single table"""
#         try:
#             # Prepare schema input for LLM definition generation
#             from app.service.models import SchemaInput
            
#             # Convert table columns to schema input format
#             columns = []
#             for col in table.columns:
#                 column_data = {
#                     "name": col.name,
#                     "display_name": col.display_name,
#                     "description": col.description,
#                     "data_type": col.data_type,
#                     "is_primary_key": col.is_primary_key,
#                     "is_nullable": col.is_nullable,
#                     "is_foreign_key": col.is_foreign_key,
#                     "usage_type": col.usage_type
#                 }
#                 columns.append(column_data)
            
#             schema_input = SchemaInput(
#                 table_name=table.name,
#                 table_description=table.description,
#                 columns=columns
#             )
            
#             # Generate LLM definitions using the schema manager service
#             documented_table = await definition_service.document_table_schema(schema_input, domain_context)
            
#             # Create definition object for MDL file
#             definition = {
#                 "table_id": table.table_id,
#                 "table_name": table.name,
#                 "display_name": table.display_name,
#                 "description": documented_table.description,
#                 "business_purpose": documented_table.business_purpose,
#                 "primary_use_cases": documented_table.primary_use_cases,
#                 "key_relationships": documented_table.key_relationships,
#                 "data_lineage": documented_table.data_lineage,
#                 "update_frequency": documented_table.update_frequency,
#                 "data_retention": documented_table.data_retention,
#                 "access_patterns": documented_table.access_patterns,
#                 "performance_considerations": documented_table.performance_considerations,
#                 "columns": []
#             }
            
#             # Add column definitions
#             for col in documented_table.columns:
#                 column_definition = {
#                     "name": col.column_name,
#                     "display_name": col.display_name,
#                     "description": col.description,
#                     "business_description": col.business_description,
#                     "usage_type": col.usage_type.value,
#                     "data_type": col.data_type,
#                     "example_values": col.example_values,
#                     "business_rules": col.business_rules,
#                     "data_quality_checks": col.data_quality_checks,
#                     "related_concepts": col.related_concepts,
#                     "privacy_classification": col.privacy_classification,
#                     "aggregation_suggestions": col.aggregation_suggestions,
#                     "filtering_suggestions": col.filtering_suggestions
#                 }
#                 definition["columns"].append(column_definition)
            
#             return {
#                 "success": True,
#                 "definition": definition
#             }
            
#         except Exception as e:
#             logger.error(f"Error generating LLM definitions for table {table.name}: {str(e)}")
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
    
#     async def _process_domain_json_schemas(self, domain: Domain, db: AsyncSession) -> Dict[str, Any]:
#         """Process domain JSON schemas and store in ChromaDB + PostgreSQL"""
#         logger.info(f"Processing domain JSON schemas for domain {domain.domain_id}")
        
#         results = {
#             "json_types_processed": [],
#             "chroma_document_ids": {},
#             "tables_processed": 0,
#             "metrics_processed": 0,
#             "views_processed": 0,
#             "calculated_columns_processed": 0,
#             "summary_created": False,
#             "errors": []
#         }
        
#         try:
#             # Initialize DomainJSONService
#             session_manager = SessionManager.get_instance()
#             domain_manager = DomainManager(None)
#             json_service = DomainJSONService(session_manager, domain_manager)
            
#             # Process all JSON types
#             json_types = [
#                 ("tables", json_service.store_domain_tables_json),
#                 ("metrics", json_service.store_domain_metrics_json),
#                 ("views", json_service.store_domain_views_json),
#                 ("calculated_columns", json_service.store_domain_calculated_columns_json),
#                 ("domain_summary", json_service.store_domain_summary_json)
#             ]
            
#             for json_type, store_func in json_types:
#                 try:
#                     logger.info(f"Processing {json_type} JSON for domain {domain.domain_id}")
                    
#                     # Store JSON in ChromaDB and PostgreSQL
#                     chroma_doc_id = await store_func(domain.domain_id, self.user_id)
                    
#                     results["json_types_processed"].append(json_type)
#                     results["chroma_document_ids"][json_type] = chroma_doc_id
                    
#                     # Update counters based on type
#                     if json_type == "tables":
#                         results["tables_processed"] = len(domain.datasets[0].tables) if domain.datasets else 0
#                     elif json_type == "metrics":
#                         # Count metrics from domain
#                         metrics_count = 0
#                         for dataset in domain.datasets:
#                             for table in dataset.tables:
#                                 metrics_count += len(table.metrics) if hasattr(table, 'metrics') else 0
#                         results["metrics_processed"] = metrics_count
#                     elif json_type == "views":
#                         # Count views from domain
#                         views_count = 0
#                         for dataset in domain.datasets:
#                             views_count += len(dataset.views) if hasattr(dataset, 'views') else 0
#                         results["views_processed"] = views_count
#                     elif json_type == "calculated_columns":
#                         # Count calculated columns from domain
#                         calc_columns_count = 0
#                         for dataset in domain.datasets:
#                             for table in dataset.tables:
#                                 for column in table.columns:
#                                     if hasattr(column, 'calculated_column') and column.calculated_column:
#                                         calc_columns_count += 1
#                         results["calculated_columns_processed"] = calc_columns_count
#                     elif json_type == "domain_summary":
#                         results["summary_created"] = True
                    
#                     logger.info(f"Successfully processed {json_type} JSON for domain {domain.domain_id}")
                    
#                 except Exception as e:
#                     error_msg = f"Error processing {json_type} JSON: {str(e)}"
#                     logger.error(error_msg)
#                     results["errors"].append(error_msg)
            
#             # Update domain metadata with JSON processing results
#             domain.json_metadata = domain.json_metadata or {}
#             domain.json_metadata["json_schemas_processing"] = {
#                 "processed_at": datetime.now().isoformat(),
#                 "processed_by": self.user_id,
#                 "json_types_processed": results["json_types_processed"],
#                 "chroma_document_ids": results["chroma_document_ids"],
#                 "summary": {
#                     "tables_processed": results["tables_processed"],
#                     "metrics_processed": results["metrics_processed"],
#                     "views_processed": results["views_processed"],
#                     "calculated_columns_processed": results["calculated_columns_processed"],
#                     "summary_created": results["summary_created"]
#                 }
#             }
            
#             await db.commit()
            
#             logger.info(f"Domain JSON schemas processing completed for domain {domain.domain_id}")
            
#         except Exception as e:
#             error_msg = f"Error in domain JSON schemas processing: {str(e)}"
#             logger.error(error_msg)
#             results["errors"].append(error_msg)
        
#         return results
    



"""
Post-Commit Service
Executes custom code and workflows when a domain is committed
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.schemas.dbmodels import Domain, Dataset, Table, SQLColumn,CalculatedColumn
from sqlalchemy.orm import selectinload
from app.service.models import DomainContext
from app.utils.sse import publish_update
from app.core.session_manager import SessionManager
from app.utils.history import DomainManager
from app.service.project_json_service import DomainJSONService
import traceback
logger = logging.getLogger(__name__)

class PostCommitService:
    """Service for executing post-commit operations"""
    
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
    
    async def execute_post_commit_workflows(self, domain_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Execute post-commit workflows for ChromaDB integration via LLM definition generation
        and domain JSON schemas processing
        
        Args:
            domain_id: ID of the committed domain
            db: Database session
            
        Returns:
            Dictionary containing execution results
        """
        logger.info(f"Executing post-commit ChromaDB integration for domain {domain_id}")
        
        results = {
            "domain_id": domain_id,
            "executed_at": datetime.now().isoformat(),
            "workflows": {},
            "status": "completed",
            "errors": [],
            "submitted_jobs": []
        }
        
        try:
            # Get domain details
            domain = await self._get_domain_with_details(domain_id, db)
            if not domain:
                raise ValueError(f"Domain {domain_id} not found")
            
            # Execute immediate workflows
            workflows = [
                ("chromadb_integration", self._setup_chromadb_integration),
                ("domain_json_schemas", self._process_domain_json_schemas)
            ]
            
            for workflow_name, workflow_func in workflows:
                try:
                    logger.info(f"Executing workflow: {workflow_name}")
                    workflow_result = await workflow_func(domain, db)
                    results["workflows"][workflow_name] = workflow_result
                    logger.info(f"Completed workflow: {workflow_name}")
                except Exception as e:
                    error_msg = f"Error in workflow {workflow_name}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
                    results["workflows"][workflow_name] = {"status": "failed", "error": str(e)}
            
            # Note: ChromaDB indexing job is automatically submitted by entity update service
            # when domain is committed, so we don't need to submit it here
            logger.info(f"ChromaDB indexing job will be submitted by entity update service for domain {domain_id}")
            
            try:
                domain_result = await db.execute(select(Domain).where(Domain.domain_id == domain_id))
                domain = domain_result.scalar_one_or_none()
                if domain:
                    domain.status = 'active'
                    db.add(domain)
                    await db.commit()
                    await db.refresh(domain)
                else:
                    logger.warning(f"Domain with ID {domain_id} not found.")
            except Exception:
                logger.error(f"Error updating domain status for domain_id={domain_id}: {traceback.format_exc()}")


            # Publish completion update
            publish_update(self.user_id, self.session_id, {
                "type": "post_commit_completed",
                "domain_id": domain_id,
                "results": results
            })
            
            logger.info(f"Post-commit ChromaDB integration completed for domain {domain_id}")
            
        except Exception as e:
            traceback.print_exc()
            error_msg = f"Error executing post-commit ChromaDB integration: {str(e)}"
            logger.error(error_msg)
            results["status"] = "failed"
            results["errors"].append(error_msg)
            
            # Publish error update
            publish_update(self.user_id, self.session_id, {
                "type": "post_commit_failed",
                "domain_id": domain_id,
                "error": str(e)
            })
        
        return results
    
    async def _get_domain_with_details(self, domain_id: str, db: AsyncSession) -> Optional[Domain]:
        """Get domain with all related details"""
        result = await db.execute(
            select(Domain)
            .options(
                selectinload(Domain.datasets)
                .selectinload(Dataset.tables),

                selectinload(Domain.datasets)
                .selectinload(Dataset.tables)
                .selectinload(Table.columns)
                .selectinload(SQLColumn.calculated_column)
                .selectinload(CalculatedColumn.function),

                selectinload(Domain.datasets)
                .selectinload(Dataset.tables)
                .selectinload(Table.metrics),

                selectinload(Domain.datasets)
                .selectinload(Dataset.tables)
                .selectinload(Table.views)
            )
        .where(Domain.domain_id == domain_id))
        return result.scalar_one_or_none()

    
    async def _setup_chromadb_integration(self, domain: Domain, db: AsyncSession) -> Dict[str, Any]:
        """Generate LLM definitions and store in temporary MDL JSON file"""
        logger.info(f"Generating LLM definitions for domain {domain.domain_id}")
        
        results = {
            "mdl_file_created": False,
            "definitions_generated": 0,
            "tables_processed": 0,
            "errors": []
        }
        
        try:
            # Get LLM definition generation service
            from app.agents.schema_manager import LLMSchemaDocumentationGenerator
            from app.core.dependencies import get_llm
            
            llm = get_llm()
            definition_service = LLMSchemaDocumentationGenerator(llm)
            
            # Prepare domain context for LLM definition generation
            domain_context = DomainContext(
                domain_id=domain.domain_id,
                domain_name=domain.display_name,
                business_domain=domain.json_metadata.get("context", {}).get("business_domain", "General"),
                purpose=domain.description or "Data domain",
                target_users=domain.json_metadata.get("context", {}).get("target_users", ["Data Analysts"]),
                key_business_concepts=domain.json_metadata.get("context", {}).get("key_business_concepts", [])
            )
            
            # Collect all table definitions
            table_definitions = []
            
            # Process each table for LLM definition generation
            for dataset in domain.datasets:
                for table in dataset.tables:
                    try:
                        logger.info(f"Generating LLM definitions for table {table.name}")
                        
                        # Generate LLM definitions
                        table_result = await self._generate_table_definitions(table, domain, definition_service, domain_context)
                        
                        if table_result["success"]:
                            table_definitions.append(table_result["definition"])
                            results["definitions_generated"] += 1
                        
                        results["tables_processed"] += 1
                        
                    except Exception as e:
                        error_msg = f"Error generating definitions for table {table.name}: {str(e)}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
            
            # Create MDL file using MDL Builder Service for ChromaDB indexing
            if table_definitions:
                try:
                    from app.services.mdl_builder_service import mdl_builder_service
                    from pathlib import Path
                    
                    # Create MDL directory if it doesn't exist
                    mdl_dir = Path("mdl_files")
                    mdl_dir.mkdir(exist_ok=True)
                    
                    # Create domain-specific directory
                    domain_mdl_dir = mdl_dir / domain.domain_id
                    domain_mdl_dir.mkdir(exist_ok=True)
                    
                    # Create MDL file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    mdl_filename = f"{domain.domain_id}_definitions_{timestamp}.json"
                    mdl_file_path = domain_mdl_dir / mdl_filename
                    
                    # Build complete MDL using the MDL Builder Service
                    mdl_content = await mdl_builder_service.build_domain_mdl(
                        domain_id=domain.domain_id,
                        db=db,
                        include_llm_definitions=True
                    )
                    
                    # Save MDL to file
                    save_result = await mdl_builder_service.save_mdl_to_file(
                        mdl_data=mdl_content,
                        file_path=str(mdl_file_path)
                    )
                    
                    if save_result["success"]:
                        results["mdl_file_created"] = True
                        results["mdl_file_path"] = str(mdl_file_path)
                        
                        # Update domain metadata
                        domain.json_metadata = domain.json_metadata or {}
                        domain.json_metadata["llm_definitions"] = {
                            "generated_at": datetime.now().isoformat(),
                            "mdl_file_path": str(mdl_file_path),
                            "definitions_count": results["definitions_generated"],
                            "tables_processed": results["tables_processed"],
                            "status": "pending_indexing"  # Will be updated by async job
                        }
                        
                        await db.commit()
                        logger.info(f"LLM definitions and MDL file created for domain {domain.domain_id}, indexing queued")
                    else:
                        logger.error(f"Error saving MDL file: {save_result['error']}")
                        results["errors"].append(f"Error saving MDL file: {save_result['error']}")
                        
                except Exception as e:
                    error_msg = f"Error creating MDL file: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
        except Exception as e:
            error_msg = f"Error in LLM definition generation: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        
        return results
    
    async def _generate_table_definitions(self, table: Table, domain: Domain, definition_service, domain_context: DomainContext) -> Dict[str, Any]:
        """Generate LLM definitions for a single table"""
        try:
            # Prepare schema input for LLM definition generation
            from app.service.models import SchemaInput
            
            # Convert table columns to schema input format
            columns = []
            for col in table.columns:
                column_data = {
                    "name": col.name,
                    "display_name": col.display_name,
                    "description": col.description,
                    "data_type": col.data_type,
                    "is_primary_key": col.is_primary_key,
                    "is_nullable": col.is_nullable,
                    "is_foreign_key": col.is_foreign_key,
                    "usage_type": col.usage_type
                }
                columns.append(column_data)
            
            schema_input = SchemaInput(
                table_name=table.name,
                table_description=table.description,
                columns=columns
            )
            
            # Generate LLM definitions using the schema manager service
            documented_table = await definition_service.document_table_schema(schema_input, domain_context)
            
            # Create definition object for MDL file
            definition = {
                "table_id": table.table_id,
                "table_name": table.name,
                "display_name": table.display_name,
                "description": documented_table.description,
                "business_purpose": documented_table.business_purpose,
                "primary_use_cases": documented_table.primary_use_cases,
                "key_relationships": documented_table.key_relationships,
                "data_lineage": documented_table.data_lineage,
                "update_frequency": documented_table.update_frequency,
                "data_retention": documented_table.data_retention,
                "access_patterns": documented_table.access_patterns,
                "performance_considerations": documented_table.performance_considerations,
                "columns": []
            }
            
            # Add column definitions
            for col in documented_table.columns:
                column_definition = {
                    "name": col.column_name,
                    "display_name": col.display_name,
                    "description": col.description,
                    "business_description": col.business_description,
                    "usage_type": col.usage_type.value,
                    "data_type": col.data_type,
                    "example_values": col.example_values,
                    "business_rules": col.business_rules,
                    "data_quality_checks": col.data_quality_checks,
                    "related_concepts": col.related_concepts,
                    "privacy_classification": col.privacy_classification,
                    "aggregation_suggestions": col.aggregation_suggestions,
                    "filtering_suggestions": col.filtering_suggestions
                }
                definition["columns"].append(column_definition)
            
            return {
                "success": True,
                "definition": definition
            }
            
        except Exception as e:
            logger.error(f"Error generating LLM definitions for table {table.name}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _process_domain_json_schemas(self, domain: Domain, db: AsyncSession) -> Dict[str, Any]:
        """Process domain JSON schemas and store in ChromaDB + PostgreSQL"""
        logger.info(f"Processing domain JSON schemas for domain {domain.domain_id}")
        
        results = {
            "json_types_processed": [],
            "chroma_document_ids": {},
            "tables_processed": 0,
            "metrics_processed": 0,
            "views_processed": 0,
            "calculated_columns_processed": 0,
            "summary_created": False,
            "errors": []
        }
        
        try:
            # Initialize DomainJSONService
            session_manager = SessionManager.get_instance()
            domain_manager = DomainManager(None)
            json_service = DomainJSONService(session_manager, domain_manager)
            
            # Process all JSON types
            json_types = [
                ("tables", json_service.store_domain_tables_json),
                ("metrics", json_service.store_domain_metrics_json),
                ("views", json_service.store_domain_views_json),
                ("calculated_columns", json_service.store_domain_calculated_columns_json),
                ("domain_summary", json_service.store_domain_summary_json)
            ]
            
            for json_type, store_func in json_types:
                try:
                    logger.info(f"Processing {json_type} JSON for domain {domain.domain_id}")
                    
                    # Store JSON in ChromaDB and PostgreSQL
                    chroma_doc_id = await store_func(domain.domain_id, self.user_id)
                    
                    results["json_types_processed"].append(json_type)
                    results["chroma_document_ids"][json_type] = chroma_doc_id
                    
                    # Update counters based on type
                    if json_type == "tables":
                        results["tables_processed"] = len(domain.datasets[0].tables) if domain.datasets else 0
                    elif json_type == "metrics":
                        # Count metrics from domain
                        metrics_count = 0
                        for dataset in domain.datasets:
                            for table in dataset.tables:
                                metrics_count += len(table.metrics) if hasattr(table, 'metrics') else 0
                        results["metrics_processed"] = metrics_count
                    elif json_type == "views":
                        # Count views from domain
                        views_count = 0
                        for dataset in domain.datasets:
                            views_count += len(dataset.views) if hasattr(dataset, 'views') else 0
                        results["views_processed"] = views_count
                    elif json_type == "calculated_columns":
                        # Count calculated columns from domain
                        calc_columns_count = 0
                        for dataset in domain.datasets:
                            for table in dataset.tables:
                                for column in table.columns:
                                    if hasattr(column, 'calculated_column') and column.calculated_column:
                                        calc_columns_count += 1
                        results["calculated_columns_processed"] = calc_columns_count
                    elif json_type == "domain_summary":
                        results["summary_created"] = True
                    
                    logger.info(f"Successfully processed {json_type} JSON for domain {domain.domain_id}")
                    
                except Exception as e:
                    traceback.print_exc()
                    error_msg = f"Error processing {json_type} JSON: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # Update domain metadata with JSON processing results
            domain.json_metadata = domain.json_metadata or {}
            domain.json_metadata["json_schemas_processing"] = {
                "processed_at": datetime.now().isoformat(),
                "processed_by": self.user_id,
                "json_types_processed": results["json_types_processed"],
                "chroma_document_ids": results["chroma_document_ids"],
                "summary": {
                    "tables_processed": results["tables_processed"],
                    "metrics_processed": results["metrics_processed"],
                    "views_processed": results["views_processed"],
                    "calculated_columns_processed": results["calculated_columns_processed"],
                    "summary_created": results["summary_created"]
                }
            }
            
            await db.commit()
            
            logger.info(f"Domain JSON schemas processing completed for domain {domain.domain_id}")
            
        except Exception as e:
            error_msg = f"Error in domain JSON schemas processing: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        
        return results
    
