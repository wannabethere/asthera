import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from tqdm import tqdm
from app.indexing.utils import helper
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy
from langchain_core.documents import Document as LangchainDocument
import json
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")


class DDLChunker:
    
    async def run(
        self,
        mdl: Dict[str, Any],
        column_batch_size: int,
        project_id: Optional[str] = None,
    ):
        """Convert DDL commands to documents with enriched metadata."""
        logger.info(f"Starting DDL chunking for project: {project_id}")
        
        def _additional_meta() -> Dict[str, Any]:
            """Extract metadata including project_id and source."""
            meta = {}
            if project_id:
                meta["project_id"] = project_id
                # Extract source from project_id (e.g., "qualys_assets" -> "qualys")
                if "_" in project_id:
                    source = project_id.split("_")[0]
                    meta["source"] = source
                else:
                    # If no underscore, use project_id as source
                    meta["source"] = project_id
            return meta

        def _extract_query_patterns(chunk: Dict[str, Any]) -> List[str]:
            """Extract query patterns from chunk metadata, prioritizing MDL properties."""
            query_patterns = []
            chunk_type = chunk.get("type", "")
            name = chunk.get("name", "")
            
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
            
            # Extract from payload if it's a dict
            payload = chunk.get("payload", "")
            if isinstance(payload, dict):
                payload_type = payload.get("type", "")
                
                if payload_type == "TABLE":
                    query_patterns.extend([
                        f"What is the structure of the {name} table?",
                        f"Show me the schema for {name}",
                        f"What columns are in {name}?",
                        f"Describe the {name} table structure"
                    ])
                elif payload_type == "TABLE_COLUMNS":
                    query_patterns.extend([
                        f"What columns are in {name}?",
                        f"Show me the column details for {name}",
                        f"What are the data types in {name}?",
                        f"Describe the columns in {name}"
                    ])
                elif payload_type == "FOREIGN_KEY":
                    query_patterns.extend([
                        f"What are the relationships for {name}?",
                        f"Show me foreign keys in {name}",
                        f"What tables does {name} relate to?",
                        f"Describe relationships for {name}"
                    ])
                elif payload_type == "VIEW":
                    query_patterns.extend([
                        f"What is the {name} view?",
                        f"Show me the view definition for {name}",
                        f"What does the {name} view contain?",
                        f"Describe the {name} view"
                    ])
                elif payload_type == "METRIC":
                    query_patterns.extend([
                        f"What metrics are available in {name}?",
                        f"Show me the metric definition for {name}",
                        f"What dimensions and measures are in {name}?",
                        f"Describe the {name} metric"
                    ])
            
            return query_patterns

        def _extract_use_cases(chunk: Dict[str, Any]) -> List[str]:
            """Extract use cases from chunk metadata, prioritizing MDL properties."""
            use_cases = []
            chunk_type = chunk.get("type", "")
            name = chunk.get("name", "")
            
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
            
            # Extract from payload if it's a dict
            payload = chunk.get("payload", "")
            if isinstance(payload, dict):
                payload_type = payload.get("type", "")
                
                if payload_type == "TABLE":
                    use_cases.extend([
                        "Table schema exploration and understanding",
                        "Database structure analysis",
                        "Column discovery and metadata lookup",
                        "Data model documentation"
                    ])
                elif payload_type == "TABLE_COLUMNS":
                    use_cases.extend([
                        "Column-level querying and filtering",
                        "Data type analysis",
                        "Primary key identification",
                        "Column metadata retrieval"
                    ])
                elif payload_type == "FOREIGN_KEY":
                    use_cases.extend([
                        "Relationship mapping and joins",
                        "Referential integrity analysis",
                        "Data lineage tracking",
                        "Join path discovery"
                    ])
                elif payload_type == "VIEW":
                    use_cases.extend([
                        "View-based querying",
                        "Precomputed query results",
                        "Data aggregation access",
                        "Simplified data access patterns"
                    ])
                elif payload_type == "METRIC":
                    use_cases.extend([
                        "Business intelligence queries",
                        "KPI and metric calculations",
                        "Analytical reporting",
                        "Performance measurement"
                    ])
            
            return use_cases

        try:
            # Get DDL commands
            logger.info("Getting DDL commands from MDL")
            ddl_commands = await self._get_ddl_commands(
                **mdl, column_batch_size=column_batch_size
            )
            logger.info(f"Found {len(ddl_commands)} DDL commands")

            # Create chunks with enriched metadata
            logger.info("Creating document chunks with enriched metadata")
            chunks = []
            for chunk in ddl_commands:
                # Extract query patterns and use cases
                query_patterns = _extract_query_patterns(chunk)
                use_cases = _extract_use_cases(chunk)
                
                # Extract source for backwards compatibility in page_content
                source = None
                if project_id and "_" in project_id:
                    source = project_id.split("_")[0]
                elif project_id:
                    source = project_id
                
                # Create rich embedding text
                # Add source to payload for backwards compatibility
                payload = chunk["payload"]
                if isinstance(payload, dict):
                    # Add source to payload dict before converting to string
                    if source:
                        payload = {**payload, "source": source}
                    payload_str = str(payload)
                else:
                    payload_str = str(payload) if payload else ""
                
                # Build enriched text with query patterns and use cases
                enriched_text_parts = [payload_str]
                
                if query_patterns:
                    enriched_text_parts.append("\n\nANSWERS THESE QUESTIONS:")
                    for pattern in query_patterns:
                        enriched_text_parts.append(f"  • {pattern}")
                
                if use_cases:
                    enriched_text_parts.append("\n\nUSE CASES AND APPLICATIONS:")
                    for use_case in use_cases:
                        enriched_text_parts.append(f"  • {use_case}")
                
                enriched_text = "\n".join(enriched_text_parts)
                
                chunk_data = {
                    "id": str(uuid.uuid4()),
                    "text": enriched_text,
                    "metadata": {
                        "type": "TABLE_SCHEMA",
                        "name": chunk["name"],
                        "query_patterns": query_patterns,
                        "use_cases": use_cases,
                        **_additional_meta(),
                    },
                    "page_content": payload_str,  # Keep original for compatibility
                }
                chunks.append(chunk_data)
            
            logger.info(f"Created {len(chunks)} document chunks with enriched metadata")

            # Convert to documents (for compatibility, but we'll use points directly)
            logger.info("Converting chunks to Langchain documents")
            documents = [
                LangchainDocument(
                    page_content=chunk["page_content"],
                    metadata=chunk["metadata"]
                )
                for chunk in tqdm(
                    chunks,
                    desc=f"Project ID: {project_id}, Converting DDL commands to documents",
                )
            ]
            logger.info(f"Successfully converted {len(documents)} chunks to documents")

            return {
                "documents": documents,
                "points_data": chunks  # Also return points_data for direct Qdrant insertion
            }
            
        except Exception as e:
            error_msg = f"Error in DDL chunking: {str(e)}"
            logger.error(error_msg)
            raise

    async def _model_preprocessor(
        self, models: List[Dict[str, Any]], **kwargs
    ) -> List[Dict[str, Any]]:
        """Preprocess models from MDL."""
       
        
        def _column_preprocessor(
            column: Dict[str, Any], table_name: str, addition: Dict[str, Any]
        ) -> Dict[str, Any]:
            addition = {
                key: helper(column, **addition)
                for key, helper in helper.COLUMN_PREPROCESSORS.items()
                if helper.condition(column, **addition)
            }
            print("column in _column_preprocessor", column)
            return {
                "name": column.get("name", ""),
                "type": column.get("type", ""),
                "table_name": table_name,
                "properties": column.get("properties", {}),  # Preserve MDL properties
                "isCalculated": column.get("isCalculated", False),  # Preserve calculated field info
                "expression": column.get("expression", ""),  # Preserve calculated field expression
                "relationship": column.get("relationship", {}),  # Preserve relationship info
                **addition,
            }

        async def _preprocessor(model: Dict[str, Any], **kwargs) -> Dict[str, Any]:
            
            addition = {
                key: await helper(model, **kwargs)
                for key, helper in helper.MODEL_PREPROCESSORS.items()
                if helper.condition(model, **kwargs)
            }

            columns = [
                _column_preprocessor(column,model.get("name"), addition)
                for column in model.get("columns", [])
                if column.get("isHidden") is not True
            ]
            return {
                "name": model.get("name", ""),
                "properties": model.get("properties", {}),
                "columns": columns,
                "primaryKey": model.get("primaryKey", ""),
            }

        try:
            tasks = [_preprocessor(model, **kwargs) for model in models]
            processed_models = await asyncio.gather(*tasks)
            logger.info(f"Successfully preprocessed {len(processed_models)} models")
            print("processed_models in model_preprocessor: ", json.dumps(processed_models, indent=2))
            return processed_models
        except Exception as e:
            error_msg = f"Error preprocessing models: {str(e)}"
            logger.error(error_msg)
            raise

    async def _get_ddl_commands(
        self,
        models: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]] = [],
        views: List[Dict[str, Any]] = [],
        metrics: List[Dict[str, Any]] = [],
        column_batch_size: int = 50,
        **kwargs,
    ) -> List[dict]:
        """Get DDL commands from MDL components."""
        logger.info("Getting DDL commands from MDL components")
        try:
            # Process models and relationships
            logger.info("Processing models and relationships")
            model_commands = self._convert_models_and_relationships(
                await self._model_preprocessor(models, **kwargs),
                relationships,
                column_batch_size,
            )
            logger.info(f"Generated {len(model_commands)} model commands")

            # Process views
            logger.info("Processing views")
            view_commands = self._convert_views(views)
            logger.info(f"Generated {len(view_commands)} view commands")

            # Process metrics
            logger.info("Processing metrics")
            metric_commands = self._convert_metrics(metrics)
            logger.info(f"Generated {len(metric_commands)} metric commands")

            # Combine all commands
            all_commands = model_commands + view_commands + metric_commands
            logger.info(f"Total DDL commands generated: {len(all_commands)}")
            return all_commands
            
        except Exception as e:
            error_msg = f"Error getting DDL commands: {str(e)}"
            logger.error(error_msg)
            raise

    def _convert_models_and_relationships(
        self,
        models: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        column_batch_size: int,
    ) -> List[str]:
        """Convert models and relationships to DDL commands."""
        logger.info("Converting models and relationships to DDL commands")
        
        def _model_command(model: Dict[str, Any]) -> dict:
            properties = model.get("properties", {})

            model_properties = {
                "alias": properties.get("displayName", ""),
                "description": properties.get("description", ""),
            }
            comment = f"\n/* {str(model_properties)} */\n"

            table_name = model["name"]
            payload = {
                "type": "TABLE",
                "comment": comment,
                "name": table_name,
            }
            # Include properties in chunk so _extract_query_patterns and _extract_use_cases can access them
            return {
                "name": table_name, 
                "payload": str(payload),
                "properties": properties  # Pass through properties for queryPatterns/useCases extraction
            }

        def _column_command(column: Dict[str, Any], model: Dict[str, Any]) -> dict:
            if column.get("relationship"):
                return None

            comments = [
                helper(column, model=model)
                for helper in helper.COLUMN_COMMENT_HELPERS.values()
                if helper.condition(column)
            ]

            return {
                "type": "COLUMN",
                "comment": "".join(comments),
                "name": column["name"],
                "data_type": column["type"],
                "is_primary_key": column["name"] == model["primaryKey"],
                # Preserve all MDL properties
                "properties": column.get("properties", {}),
                "isCalculated": column.get("isCalculated", False),
                "expression": column.get("expression", ""),
                "relationship": column.get("relationship", {}),
                "notNull": column.get("notNull", False)
            }

        def _relationship_command(
            relationship: Dict[str, Any],
            table_name: str,
            primary_keys_map: Dict[str, str],
        ) -> dict:
            condition = relationship.get("condition", "")
            join_type = relationship.get("joinType", "")
            models = relationship.get("models", [])

            if len(models) != 2:
                return None

            if table_name not in models:
                return None

            if join_type not in ["MANY_TO_ONE", "ONE_TO_MANY", "ONE_TO_ONE"]:
                return None

            # Get related table and foreign key column
            is_source = table_name == models[0]
            related_table = models[1] if is_source else models[0]
            condition_parts = condition.split(" = ")
            fk_column = condition_parts[0 if is_source else 1].split(".")[1]

            # Check if related table exists in current MDL file
            if related_table not in primary_keys_map:
                logger.warning(
                    f"Skipping relationship from {table_name} to {related_table}: "
                    f"related table not found in current MDL file's primary_keys_map"
                )
                return None
            
            # Check if primary key exists and is not empty
            related_primary_key = primary_keys_map.get(related_table)
            if not related_primary_key:
                logger.warning(
                    f"Skipping relationship from {table_name} to {related_table}: "
                    f"related table has no primary key defined"
                )
                return None

            # Build foreign key constraint
            fk_constraint = f"FOREIGN KEY ({fk_column}) REFERENCES {related_table}({related_primary_key})"

            return {
                "type": "FOREIGN_KEY",
                "comment": f'-- {{"condition": {condition}, "joinType": {join_type}}}\n  ',
                "constraint": fk_constraint,
                "tables": models,
            }

        def _column_batch(
            model: Dict[str, Any], primary_keys_map: Dict[str, str]
        ) -> List[dict]:
            commands = [
                _column_command(column, model) for column in model["columns"]
            ] + [
                _relationship_command(relationship, model["name"], primary_keys_map)
                for relationship in relationships
            ]

            filtered = [command for command in commands if command is not None]

            # Include model properties in each column batch chunk
            model_properties = model.get("properties", {})
            return [
                {
                    "name": model["name"],
                    "payload": str(
                        {
                            "type": "TABLE_COLUMNS",
                            "columns": filtered[i : i + column_batch_size],
                        }
                    ),
                    "properties": model_properties  # Pass through properties for queryPatterns/useCases extraction
                }
                for i in range(0, len(filtered), column_batch_size)
            ]

        try:
            # A map to store model primary keys for foreign key relationships
            primary_keys_map = {model["name"]: model["primaryKey"] for model in models}

            commands = [
                command
                for model in models
                for command in _column_batch(model, primary_keys_map)
                + [_model_command(model)]
            ]
            logger.info(f"Generated {len(commands)} model and relationship commands")
            
            return commands
            
        except Exception as e:
            error_msg = f"Error converting models and relationships: {str(e)}"
            logger.error(error_msg)
            raise

    def _convert_views(self, views: List[Dict[str, Any]]) -> List[str]:
        """Convert views to DDL commands."""
        logger.info("Converting views to DDL commands")
        try:
            def _payload(view: Dict[str, Any]) -> dict:
                return {
                    "type": "VIEW",
                    "comment": f"/* {view['properties']} */\n"
                    if "properties" in view
                    else "",
                    "name": view["name"],
                    "statement": view["statement"],
                }

            commands = [
                {
                    "name": view["name"], 
                    "payload": str(_payload(view)),
                    "properties": view.get("properties", {})  # Pass through properties for queryPatterns/useCases extraction
                } 
                for view in views
            ]
            logger.info(f"Generated {len(commands)} view commands")
            return commands
            
        except Exception as e:
            error_msg = f"Error converting views: {str(e)}"
            logger.error(error_msg)
            raise

    def _convert_metrics(self, metrics: List[Dict[str, Any]]) -> List[str]:
        """Convert metrics to DDL commands."""
        logger.info("Converting metrics to DDL commands")
        try:
            def _create_column(name: str, data_type: str, comment: str) -> dict:
                return {
                    "type": "COLUMN",
                    "comment": comment,
                    "name": name,
                    "data_type": data_type,
                }

            def _dimensions(metric: Dict[str, Any]) -> List[dict]:
                return [
                    _create_column(
                        name=dim.get("name", ""),
                        data_type=dim.get("type", ""),
                        comment="-- This column is a dimension\n  ",
                    )
                    for dim in metric.get("dimension", [])
                ]

            def _measures(metric: Dict[str, Any]) -> List[dict]:
                return [
                    _create_column(
                        name=measure.get("name", ""),
                        data_type=measure.get("type", ""),
                        comment="-- This column is a measure\n  ",
                    )
                    for measure in metric.get("measure", [])
                ]

            def _payload(metric: Dict[str, Any]) -> dict:
                return {
                    "type": "METRIC",
                    "comment": f"/* {metric['properties']} */\n"
                    if "properties" in metric
                    else "",
                    "name": metric["name"],
                    "columns": _dimensions(metric) + _measures(metric),
                }

            commands = [
                {
                    "name": metric["name"], 
                    "payload": str(_payload(metric)),
                    "properties": metric.get("properties", {})  # Pass through properties for queryPatterns/useCases extraction
                }
                for metric in metrics
            ]
            
           
            logger.info(f"Generated {len(commands)} metric commands")
            return commands
            
        except Exception as e:
            error_msg = f"Error converting metrics: {str(e)}"
            logger.error(error_msg)
            raise

"""
page_content='{'type': 'METRIC', 'comment': "/* {'displayName': 'Admin Dashboard Metrics', 'description': 'Comprehensive metrics for admin dashboard views'} */\n", 'name': 'admin_dashboard_metrics', 'columns': [{'type': 'COLUMN', 'comment': '-- This column is a dimension\n  ', 'name': 'PrimaryDomain', 'data_type': 'VARCHAR'}, {'type': 'COLUMN', 'comment': '-- This column is a dimension\n  ', 'name': 'PrimaryOrganization', 'data_type': 'VARCHAR'}, {'type': 'COLUMN', 'comment': '-- This column is a dimension\n  ', 'name': 'ActivityType', 'data_type': 'VARCHAR'}, {'type': 'COLUMN', 'comment': '-- This column is a dimension\n  ', 'name': 'TrainingStatus', 'data_type': 'VARCHAR'}, {'type': 'COLUMN', 'comment': '-- This column is a dimension\n  ', 'name': 'assignment_mode', 'data_type': 'VARCHAR'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'total_users', 'data_type': 'INTEGER'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'certified_users', 'data_type': 'INTEGER'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'certification_completion_rate', 'data_type': 'DECIMAL'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'total_trainings', 'data_type': 'INTEGER'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'completed_trainings', 'data_type': 'INTEGER'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'overdue_trainings_count', 'data_type': 'INTEGER'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'compliant_users', 'data_type': 'INTEGER'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'compliance_rate', 'data_type': 'DECIMAL'}, {'type': 'COLUMN', 'comment': '-- This column is a measure\n  ', 'name': 'upcoming_expirations', 'data_type': 'INTEGER'}]}' metadata={'type': 'TABLE_SCHEMA', 'name': 'admin_dashboard_metrics', 'project_id': 'employee_training'}
Table documents are written in this format.
"""
class DBSchema:
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        column_batch_size: Optional[int] = 200,
    ) -> None:
        """Initialize the DB Schema processor."""
        logger.info("Initializing DB Schema processor")
        self._document_store = document_store
        self._embedder = embedder
        self._chunker = DDLChunker()
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )
        self._column_batch_size = column_batch_size
        logger.info("DB Schema processor initialized successfully")

    async def run(
        self, mdl_str: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process and index DB schema."""
        logger.info(f"Starting DB schema processing for project: {project_id}")
        
        try:
            # Parse MDL string
            logger.info("Parsing MDL string")
            import json
            mdl = json.loads(mdl_str)
            logger.info("MDL string parsed successfully")
            
            # Convert to documents
            logger.info("Converting MDL to documents")
            doc_result = await self._chunker.run(
                mdl=mdl,
                column_batch_size=self._column_batch_size,
                project_id=project_id,
            )
            logger.info(f"Created {len(doc_result['documents'])} documents")
            
            # Check if document_store is Qdrant-based and use direct points
            from app.storage.qdrant_store import DocumentQdrantStore
            if isinstance(self._document_store, DocumentQdrantStore):
                logger.info("Using direct Qdrant points insertion for DB schema")
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
            
            logger.info(f"DB schema processing completed successfully: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Error processing DB schema: {str(e)}"
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
        collection_name="db_schema"
    )
    
    logger.info("Creating DB Schema processor")
    processor = DBSchema(
        document_store=doc_store,
        embedder=embeddings
    )
    
    # Example MDL string
    logger.info("Processing test MDL string")
    mdl_str = '{"models": [], "views": [], "relationships": [], "metrics": []}'
    
    # Process the DB schema
    logger.info("Starting test processing")
    import asyncio
    result = asyncio.run(processor.run(mdl_str, project_id="test"))
    logger.info(f"Test processing completed: {result}")

