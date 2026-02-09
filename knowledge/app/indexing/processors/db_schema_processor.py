"""
DB Schema Processor
Processes and indexes database schema from MDL using DBSchema structure.
Uses the same helper system as agents/app/indexing/db_schema.py for consistency.
"""
import logging
import uuid
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.documents import Document

# Import helper functions (same logic as original db_schema.py)
try:
    from app.indexing.utils.helper import (
        COLUMN_PREPROCESSORS,
        COLUMN_COMMENT_HELPERS,
        MODEL_PREPROCESSORS,
        Helper
    )
    # Create a helper module-like object for compatibility
    class HelperModule:
        COLUMN_PREPROCESSORS = COLUMN_PREPROCESSORS
        COLUMN_COMMENT_HELPERS = COLUMN_COMMENT_HELPERS
        MODEL_PREPROCESSORS = MODEL_PREPROCESSORS
    helper = HelperModule()
except ImportError:
    # If helper not available, create minimal stubs
    logger.warning("Helper module not found, using simplified processing")
    helper = None

logger = logging.getLogger(__name__)


class DBSchemaProcessor:
    """Processes database schema from MDL and creates documents in DBSchema format."""
    
    def __init__(self, column_batch_size: int = 200):
        """
        Initialize the DB Schema processor.
        
        Args:
            column_batch_size: Number of columns to include per document batch
        """
        self.column_batch_size = column_batch_size
        logger.info(f"Initializing DBSchemaProcessor with column_batch_size={column_batch_size}")
    
    async def process_models(
        self,
        models: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]] = [],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Preprocess models from MDL using the same helper system as db_schema.py.
        
        Args:
            models: List of model dictionaries from MDL
            relationships: List of relationship dictionaries
            **kwargs: Additional parameters
            
        Returns:
            List of processed model dictionaries
        """
        logger.info(f"Preprocessing {len(models)} models")
        
        def _column_preprocessor(
            column: Dict[str, Any], table_name: str, addition: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Preprocess a single column using helper.COLUMN_PREPROCESSORS."""
            if helper and hasattr(helper, 'COLUMN_PREPROCESSORS'):
                # Use helper system like original db_schema.py
                addition = {
                    key: helper_func(column, **addition)
                    for key, helper_func in helper.COLUMN_PREPROCESSORS.items()
                    if helper_func.condition(column, **addition)
                }
            else:
                # Fallback: manual extraction
                addition = {}
                if "properties" in column:
                    addition["properties"] = column.get("properties")
                if "relationship" in column:
                    addition["relationship"] = column.get("relationship")
                if "expression" in column:
                    addition["expression"] = column.get("expression")
                if column.get("isCalculated", False):
                    addition["isCalculated"] = column.get("isCalculated")
            
            return {
                "name": column.get("name", ""),
                "type": column.get("type", ""),
                "table_name": table_name,
                "properties": column.get("properties", {}),
                "isCalculated": column.get("isCalculated", False),
                "expression": column.get("expression", ""),
                "relationship": column.get("relationship", {}),
                "notNull": column.get("notNull", False),
                **addition,
            }
        
        async def _preprocessor(model: Dict[str, Any], **kwargs) -> Dict[str, Any]:
            """Preprocess a single model using helper.MODEL_PREPROCESSORS."""
            if helper and hasattr(helper, 'MODEL_PREPROCESSORS'):
                # Use helper system like original db_schema.py
                addition = {
                    key: await helper_func(model, **kwargs)
                    for key, helper_func in helper.MODEL_PREPROCESSORS.items()
                    if helper_func.condition(model, **kwargs)
                }
            else:
                addition = {}
            
            columns = [
                _column_preprocessor(column, model.get("name"), addition)
                for column in model.get("columns", [])
                if column.get("isHidden") is not True
            ]
            properties = model.get("properties", {})
            return {
                "name": model.get("name", ""),
                "properties": properties,
                "columns": columns,
                "primaryKey": model.get("primaryKey", ""),
                "category": properties.get("category"),  # Extract category from properties
            }
        
        try:
            tasks = [_preprocessor(model, **kwargs) for model in models]
            processed_models = await asyncio.gather(*tasks)
            logger.info(f"Successfully preprocessed {len(processed_models)} models")
            return processed_models
        except Exception as e:
            error_msg = f"Error preprocessing models: {str(e)}"
            logger.error(error_msg)
            raise
    
    def convert_models_to_ddl_commands(
        self,
        processed_models: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        column_batch_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert processed models to DDL command documents.
        
        Args:
            processed_models: List of preprocessed model dictionaries
            relationships: List of relationship dictionaries
            column_batch_size: Override default column batch size
            
        Returns:
            List of DDL command dictionaries
        """
        column_batch_size = column_batch_size or self.column_batch_size
        logger.info(f"Converting {len(processed_models)} models to DDL commands")
        
        def _model_command(model: Dict[str, Any]) -> Dict[str, Any]:
            """Create a model command."""
            properties = model.get("properties", {})
            model_properties = {
                "alias": properties.get("displayName", ""),
                "description": properties.get("description", ""),
            }
            comment = f"\n/* {str(model_properties)} */\n"
            
            table_name = model["name"]
            category = model.get("category")  # Get category from processed model
            payload = {
                "type": "TABLE",
                "comment": comment,
                "name": table_name,
            }
            return {
                "name": table_name,
                "payload": str(payload),
                "category": category  # Include category in command
            }
        
        def _column_command(column: Dict[str, Any], model: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Create a column command using helper.COLUMN_COMMENT_HELPERS."""
            if column.get("relationship"):
                return None
            
            # Use helper system for comment generation like original db_schema.py
            if helper and hasattr(helper, 'COLUMN_COMMENT_HELPERS'):
                comments = [
                    helper_func(column, model=model)
                    for helper_func in helper.COLUMN_COMMENT_HELPERS.values()
                    if helper_func.condition(column)
                ]
            else:
                # Fallback: simplified comment generation
                comments = []
                if column.get("properties", {}).get("displayName"):
                    comments.append(f"-- {column['properties']['displayName']}\n  ")
                if column.get("properties", {}).get("description"):
                    comments.append(f"-- {column['properties']['description']}\n  ")
            
            return {
                "type": "COLUMN",
                "comment": "".join(comments),
                "name": column["name"],
                "data_type": column["type"],
                "is_primary_key": column["name"] == model["primaryKey"],
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
        ) -> Optional[Dict[str, Any]]:
            """Create a relationship command."""
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
            
            # Build foreign key constraint
            fk_constraint = f"FOREIGN KEY ({fk_column}) REFERENCES {related_table}({primary_keys_map[related_table]})"
            
            return {
                "type": "FOREIGN_KEY",
                "comment": f'-- {{"condition": {condition}, "joinType": {join_type}}}\n  ',
                "constraint": fk_constraint,
                "tables": models,
            }
        
        def _column_batch(
            model: Dict[str, Any], primary_keys_map: Dict[str, str]
        ) -> List[Dict[str, Any]]:
            """Create column batch commands."""
            commands = [
                _column_command(column, model) for column in model["columns"]
            ] + [
                _relationship_command(relationship, model["name"], primary_keys_map)
                for relationship in relationships
            ]
            
            filtered = [command for command in commands if command is not None]
            category = model.get("category")  # Get category from processed model
            
            return [
                {
                    "name": model["name"],
                    "payload": str({
                        "type": "TABLE_COLUMNS",
                        "columns": filtered[i : i + column_batch_size],
                    }),
                    "category": category  # Include category in command
                }
                for i in range(0, len(filtered), column_batch_size)
            ]
        
        try:
            # Create primary keys map
            primary_keys_map = {model["name"]: model["primaryKey"] for model in processed_models}
            
            commands = [
                command
                for model in processed_models
                for command in _column_batch(model, primary_keys_map)
                + [_model_command(model)]
            ]
            
            logger.info(f"Generated {len(commands)} model and relationship commands")
            return commands
            
        except Exception as e:
            error_msg = f"Error converting models to DDL commands: {str(e)}"
            logger.error(error_msg)
            raise
    
    def convert_views_to_ddl_commands(self, views: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert views to DDL commands.
        
        Args:
            views: List of view dictionaries from MDL
            
        Returns:
            List of DDL command dictionaries
        """
        logger.info(f"Converting {len(views)} views to DDL commands")
        
        def _payload(view: Dict[str, Any]) -> dict:
            return {
                "type": "VIEW",
                "comment": f"/* {view['properties']} */\n" if "properties" in view else "",
                "name": view["name"],
                "statement": view["statement"],
            }
        
        commands = []
        for view in views:
            category = view.get("properties", {}).get("category")  # Extract category from view properties
            command = {
                "name": view["name"],
                "payload": str(_payload(view))
            }
            if category:
                command["category"] = category
            commands.append(command)
        
        logger.info(f"Generated {len(commands)} view commands")
        return commands
    
    def convert_metrics_to_ddl_commands(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert metrics to DDL commands.
        
        Args:
            metrics: List of metric dictionaries from MDL
            
        Returns:
            List of DDL command dictionaries
        """
        logger.info(f"Converting {len(metrics)} metrics to DDL commands")
        
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
                "comment": f"/* {metric['properties']} */\n" if "properties" in metric else "",
                "name": metric["name"],
                "columns": _dimensions(metric) + _measures(metric),
            }
        
        commands = []
        for metric in metrics:
            category = metric.get("properties", {}).get("category")  # Extract category from metric properties
            command = {
                "name": metric["name"],
                "payload": str(_payload(metric))
            }
            if category:
                command["category"] = category
            commands.append(command)
        
        logger.info(f"Generated {len(commands)} metric commands")
        return commands
    
    def create_documents(
        self,
        ddl_commands: List[Dict[str, Any]],
        project_id: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Create Document objects from DDL commands.
        
        Args:
            ddl_commands: List of DDL command dictionaries
            project_id: Project ID
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            List of Document objects in DBSchema format
        """
        logger.info(f"Creating {len(ddl_commands)} documents from DDL commands")
        
        documents = []
        for command in ddl_commands:
            doc_metadata = {
                "type": "TABLE_SCHEMA",
                "name": command["name"],
                "content_type": "db_schema",
                "indexed_at": datetime.utcnow().isoformat()
            }
            
            # Add category if available (for LLM guidance, not database filtering)
            if command.get("category"):
                doc_metadata["category"] = command["category"]
            
            # Add optional fields
            if project_id:
                doc_metadata["project_id"] = project_id
            if product_name:
                doc_metadata["product_name"] = product_name
            if domain:
                doc_metadata["domain"] = domain
            if metadata:
                doc_metadata.update(metadata)
            
            doc = Document(
                page_content=command["payload"],
                metadata=doc_metadata
            )
            documents.append(doc)
        
        logger.info(f"Created {len(documents)} documents")
        return documents
    
    async def process_mdl(
        self,
        mdl: Dict[str, Any],
        project_id: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Process MDL and create DB schema documents.
        
        Args:
            mdl: MDL dictionary
            project_id: Project ID
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            List of Document objects
        """
        logger.info(f"Processing MDL for DB schema (project: {project_id}, domain: {domain})")
        
        # Process models
        processed_models = await self.process_models(
            models=mdl.get("models", []),
            relationships=mdl.get("relationships", [])
        )
        
        # Convert to DDL commands
        model_commands = self.convert_models_to_ddl_commands(
            processed_models=processed_models,
            relationships=mdl.get("relationships", [])
        )
        
        # Process views
        view_commands = self.convert_views_to_ddl_commands(mdl.get("views", []))
        
        # Process metrics
        metric_commands = self.convert_metrics_to_ddl_commands(mdl.get("metrics", []))
        
        # Combine all commands
        all_commands = model_commands + view_commands + metric_commands
        logger.info(f"Total DDL commands generated: {len(all_commands)}")
        
        # Create documents
        documents = self.create_documents(
            ddl_commands=all_commands,
            project_id=project_id or product_name,
            product_name=product_name,
            domain=domain,
            metadata=metadata
        )
        
        return documents

