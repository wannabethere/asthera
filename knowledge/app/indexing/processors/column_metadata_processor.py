"""
Column Metadata Processor
Processes column metadata from MDL and produces documents for the column_metadata store.
Same structure and logging as agents/app/indexing/project_reader._process_column_metadata.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _get_formatted_comment(column: Dict[str, Any], column_name: str) -> str:
    """Build comment from displayName/description or fallback to column name."""
    try:
        from app.indexing.utils.helper import _properties_comment
    except ImportError:
        _properties_comment = None
    properties = column.get("properties", {})
    display_name = properties.get("displayName", "")
    description = properties.get("description", "")
    column_for_helper = {"properties": {"displayName": display_name, "description": description}}
    if _properties_comment:
        formatted_comment = _properties_comment(column_for_helper).strip()
    else:
        formatted_comment = ""
    if not formatted_comment or formatted_comment == "-- {}":
        if display_name or description:
            parts = []
            if display_name:
                parts.append(display_name)
            if description and description != display_name:
                parts.append(description)
            formatted_comment = " -- ".join(parts)
        else:
            formatted_comment = column_name.replace("_", " ").title()
            logger.debug("Generated comment for column %s: %s", column_name, formatted_comment)
    return formatted_comment or column_name.replace("_", " ").title()


class ColumnMetadataProcessor:
    """Process column metadata from MDL and create documents for column_metadata store."""

    def __init__(self):
        logger.info("Initializing ColumnMetadataProcessor")

    async def process_mdl(
        self,
        mdl: Dict[str, Any],
        project_id: str,
        product_name: Optional[str] = None,
    ) -> Tuple[List[Document], Dict[str, Any]]:
        """
        Process column metadata from MDL. Same behavior and logging as agents _process_column_metadata.
        Returns (documents, result_dict).
        """
        logger.info("Starting column metadata processing for project: %s", project_id)
        product_name = product_name or project_id
        documents = []
        total_columns = 0
        try:
            for model in mdl.get("models", []):
                table_name = model.get("name", "")
                if not table_name:
                    continue
                logger.info("Processing columns for table: %s", table_name)
                for column in model.get("columns", []):
                    column_name = column.get("name", "")
                    if not column_name:
                        continue
                    properties = column.get("properties", {})
                    display_name = properties.get("displayName", "")
                    description = properties.get("description", "")
                    column_type = column.get("type", "VARCHAR")
                    formatted_comment = _get_formatted_comment(column, column_name)
                    column_metadata = {
                        "column_name": column_name,
                        "table_name": table_name,
                        "type": column_type,
                        "display_name": display_name,
                        "description": description,
                        "comment": formatted_comment,
                        "is_calculated": column.get("isCalculated", False),
                        "expression": column.get("expression", ""),
                        "is_primary_key": column.get("name", "") == model.get("primaryKey", ""),
                        "is_foreign_key": "relationship" in column,
                        "relationship": column.get("relationship", {}),
                        "properties": properties,
                        "not_null": column.get("notNull", False),
                    }
                    doc_content = json.dumps(column_metadata)
                    doc_metadata = {
                        "type": "COLUMN_METADATA",
                        "project_id": project_id,
                        "product_name": product_name,
                        "table_name": table_name,
                        "column_name": column_name,
                        "data_type": column.get("type", "VARCHAR"),
                        "display_name": display_name,
                        "description": (description[:100] if description else ""),
                        "comment": (formatted_comment[:100] if formatted_comment else ""),
                        "is_calculated": column.get("isCalculated", False),
                        "is_primary_key": column.get("name", "") == model.get("primaryKey", ""),
                        "is_foreign_key": "relationship" in column,
                    }
                    documents.append(Document(page_content=doc_content, metadata=doc_metadata))
                    total_columns += 1
                    logger.info(
                        "Column %s.%s: display_name='%s', description='%s'",
                        table_name,
                        column_name,
                        display_name,
                        (description[:50] + "..." if description and len(description) > 50 else (description or "None")),
                    )
            result = {
                "documents_written": len(documents),
                "total_columns": total_columns,
                "project_id": project_id,
            }
            logger.info("Storing %s column metadata documents", len(documents))
            logger.info("Column metadata processing completed successfully: %s", result)
            return documents, result
        except Exception as e:
            logger.exception("Error processing column metadata: %s", e)
            return [], {
                "documents_written": 0,
                "total_columns": 0,
                "project_id": project_id,
                "error": str(e),
            }