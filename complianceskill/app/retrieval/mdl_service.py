"""
MDL Retrieval Service

Retrieval service for MDL collections (leen_db_schema, leen_table_description,
leen_project_meta, leen_metrics_registry) or CSOD collections (csod_db_schema,
csod_table_descriptions, csod_metrics_registry).

Uses the same document parsing logic as agents/app/agents/retrieval/retrieval.py
to handle empty content by extracting from metadata.

Supports workflow-specific collections via MDLCollectionFactory:
- workflow_type="csod" → uses csod_* collections
- workflow_type="dt" or "leen" → uses leen_* collections (default)
"""
import logging
import ast
from typing import Dict, List, Optional, Any, Literal
import hashlib
import json

from app.core.dependencies import get_doc_store_provider
from app.ingestion.embedder import EmbeddingService
from app.utils.cache import InMemoryCache
from app.storage.mdl_collection_factory import MDLCollectionFactory, WorkflowType
from app.retrieval.mdl_results import (
    MDLSchemaResult,
    MDLTableDescriptionResult,
    MDLProjectMetaResult,
    MDLMetricResult,
    MDLDashboardPatternResult,
    MDLRetrievedContext,
)

logger = logging.getLogger(__name__)


def build_schema_ddl(schemas: List[Dict[str, Any]]) -> str:
    """
    Build DDL for each resolved schema. One DDL block per table.
    Includes table description and column descriptions (from properties.description).
    Misses (tables not in resolved_schemas) are ignored — we only include what we have.

    Reusable across retrieval services and agents.
    """
    parts = []
    for s in schemas or []:
        table_name = s.get("table_name", "") or s.get("name", "")
        if not table_name:
            continue
        table_desc = (s.get("description", "") or "").strip()
        ddl = s.get("table_ddl", "")
        col_meta = s.get("column_metadata", []) or s.get("columns", [])

        block_lines = [f"### {table_name}"]
        if table_desc:
            block_lines.append(f"Table description: {table_desc[:500]}{'...' if len(table_desc) > 500 else ''}")

        if ddl and ddl.strip():
            block_lines.append(f"```sql\n{ddl.strip()}\n```")
        elif col_meta:
            col_entries = []
            for c in col_meta:
                if isinstance(c, dict):
                    col_name = c.get("column_name") or c.get("name", "")
                    col_type = c.get("type", "")
                    props = c.get("properties", {}) or {}
                    col_desc = props.get("description") or c.get("description", "")
                    if col_name:
                        entry = f"  - {col_name}"
                        if col_type:
                            entry += f" ({col_type})"
                        if col_desc:
                            entry += f" — {str(col_desc)[:120]}{'...' if len(str(col_desc)) > 120 else ''}"
                        col_entries.append(entry)
                else:
                    col_entries.append(f"  - {str(c)}")
            block_lines.append("Columns:")
            block_lines.extend(col_entries)
        else:
            block_lines.append("(no DDL or columns)")

        parts.append("\n".join(block_lines))
    return "\n\n".join(parts) if parts else "(no schemas)"


class MDLRetrievalService:
    """
    Retrieval service for MDL collections.
    
    Supports workflow-specific collections:
    - workflow_type="csod" → uses csod_db_schema, csod_table_descriptions, csod_metrics_registry
    - workflow_type="dt" or "leen" → uses leen_db_schema, leen_table_description, leen_metrics_registry
    """
    
    def __init__(
        self,
        doc_store_provider=None,
        embedder: Optional[EmbeddingService] = None,
        workflow_type: WorkflowType = "dt"
    ):
        """
        Initialize MDL retrieval service.
        
        Args:
            doc_store_provider: Optional DocumentStoreProvider instance
            embedder: Optional EmbeddingService instance
            workflow_type: "csod" for CSOD workflow, "dt" or "leen" for DT/LEEN workflow (default: "dt")
        """
        self._embedder = embedder or EmbeddingService()
        self._doc_stores = doc_store_provider or get_doc_store_provider()
        self._cache = InMemoryCache()
        self._workflow_type = workflow_type
        
        # Get collection names for this workflow
        self._collection_factory = MDLCollectionFactory(workflow_type=workflow_type)
        db_schema_collection = self._collection_factory.get_db_schema_collection()
        table_desc_collection = self._collection_factory.get_table_description_collection()
        project_meta_collection = self._collection_factory.get_project_meta_collection()
        metrics_registry_collection = self._collection_factory.get_metrics_registry_collection()
        dashboards_collection = self._collection_factory.get_dashboards_collection()
        
        # Get MDL document stores using workflow-specific collection names
        stores = self._doc_stores.stores if hasattr(self._doc_stores, 'stores') else {}
        self._db_schema_store = stores.get(db_schema_collection)
        self._table_desc_store = stores.get(table_desc_collection)
        self._project_meta_store = stores.get(project_meta_collection)
        self._metrics_store = stores.get(metrics_registry_collection)
        self._dashboard_store = stores.get(dashboards_collection)  # Retrieved from factory, can be workflow-specific in future
        
        if not any([self._db_schema_store, self._table_desc_store, 
                   self._project_meta_store, self._metrics_store, self._dashboard_store]):
            logger.warning(
                f"No MDL document stores found for workflow_type={workflow_type}. "
                f"Expected collections: {db_schema_collection}, {table_desc_collection}, "
                f"{metrics_registry_collection}, mdl_dashboards. "
                f"MDL retrieval may not work."
            )
    
    def _get_cache_key(self, method: str, *args) -> str:
        """Generate cache key from method name and arguments."""
        key_data = {"method": method, "args": args}
        return hashlib.sha256(
            json.dumps(key_data, sort_keys=True, default=str).encode()
        ).hexdigest()
    
    def _format_result(self, result: Dict, collection_type: str = "") -> Optional[Dict[str, Any]]:
        """Format raw document store result into structured format.
        
        Args:
            result: Raw result from document store
            collection_type: Type of collection (for logging/debugging)
        
        Returns:
            Formatted dict with content, metadata, score, id or None if error
        """
        try:
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            score = result.get("score", 0.0)
            doc_id = result.get("id", "")
            
            # Try to parse content if it's a JSON string
            parsed_content = content
            if isinstance(content, str):
                try:
                    parsed_content = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    # Keep as string if not JSON
                    pass
            
            return {
                "content": parsed_content if isinstance(parsed_content, dict) else content,
                "metadata": metadata,
                "score": score,
                "id": doc_id
            }
        except Exception as e:
            logger.warning(f"Error formatting {collection_type} result: {e}")
            return None
    
    def _parse_doc_content(self, doc) -> dict:
        """Safely parse the 'content' field from a document and return a dict.
        
        This method is copied from agents/app/agents/retrieval/retrieval.py
        to handle empty content by building dict from metadata (common with Qdrant points).
        
        Handles both Langchain documents and direct Qdrant points with enriched metadata.
        When content is empty, builds dict from metadata.
        """
        content = doc.get('content', '')
        metadata = doc.get('metadata', {})
        
        logger.debug(f"DEBUG: _parse_doc_content - raw content length: {len(content) if content else 0}")
        logger.debug(f"DEBUG: _parse_doc_content - metadata keys: {list(metadata.keys()) if metadata else 'None'}")
        
        # Check if this is a direct Qdrant point with enriched text
        # Direct points have enriched text that includes query_patterns and use_cases
        # We need to extract the original content (before enrichment)
        if content and ("ANSWERS THESE QUESTIONS:" in content or "USE CASES AND APPLICATIONS:" in content):
            # This is enriched content - extract the original content before enrichment markers
            logger.debug("Detected enriched content, extracting original content")
            lines = content.split('\n')
            original_lines = []
            for line in lines:
                if line.strip() == "ANSWERS THESE QUESTIONS:" or line.strip() == "USE CASES AND APPLICATIONS:":
                    break
                original_lines.append(line)
            content = '\n'.join(original_lines).strip()
            logger.debug(f"Extracted original content: {content[:200]}...")
        
        # If content is empty, build dict from metadata (common with Qdrant points)
        if not content or not content.strip():
            logger.debug("DEBUG: _parse_doc_content - no content found, building from metadata")
            # Build a dict from metadata that matches expected structure
            # Copy all metadata fields to preserve all information including columns
            parsed = {}
            for key, value in metadata.items():
                parsed[key] = value
            # Ensure essential fields are set
            if "type" not in parsed:
                parsed["type"] = metadata.get("type", "")
            if "name" not in parsed:
                parsed["name"] = metadata.get("name", "")
            if "table_name" not in parsed:
                parsed["table_name"] = metadata.get("table_name", "")
            if "description" not in parsed:
                parsed["description"] = metadata.get("description", "")
            if "mdl_type" not in parsed:
                parsed["mdl_type"] = metadata.get("mdl_type", "")
            if "relationships" not in parsed:
                parsed["relationships"] = metadata.get("relationships", [])
            # Preserve columns if they exist in metadata - CRITICAL for column information
            if "columns" in metadata:
                columns_value = metadata.get("columns", [])
                parsed["columns"] = columns_value
                logger.debug(f"DEBUG: _parse_doc_content - preserved {len(columns_value) if isinstance(columns_value, list) else 'N/A'} columns from metadata for {parsed.get('name', 'unknown')}")
            else:
                logger.warning(f"DEBUG: _parse_doc_content - NO COLUMNS in metadata for {parsed.get('name', 'unknown')}")
            logger.debug(f"DEBUG: _parse_doc_content - built from metadata: {parsed.get('name', 'unknown')}")
            return parsed
        
        # Check if content looks like it could be a dict/JSON before trying to parse
        # If it's just plain text (like a description), use metadata directly
        content_stripped = content.strip("'").strip('"').strip()
        
        # If content doesn't start with { or [, it's likely plain text, not a dict/JSON
        if not content_stripped.startswith(('{', '[')):
            logger.debug(f"Content appears to be plain text, using metadata directly: {content[:100]}...")
            # Build from metadata - this preserves all column information from metadata
            parsed = {}
            # Copy all metadata fields first
            for key, value in metadata.items():
                parsed[key] = value
            # If content is a description, add it
            if content_stripped and not parsed.get("description"):
                parsed["description"] = content_stripped
            # Ensure we have all essential fields
            if "type" not in parsed:
                parsed["type"] = metadata.get("type", "")
            if "name" not in parsed:
                parsed["name"] = metadata.get("name", "")
            if "table_name" not in parsed:
                parsed["table_name"] = metadata.get("table_name", "")
            if "mdl_type" not in parsed:
                parsed["mdl_type"] = metadata.get("mdl_type", "")
            if "relationships" not in parsed:
                parsed["relationships"] = metadata.get("relationships", [])
            # Preserve columns if they exist in metadata
            if "columns" in metadata:
                parsed["columns"] = metadata.get("columns", [])
            logger.debug(f"DEBUG: _parse_doc_content - built from metadata (plain text content): {parsed.get('name', 'unknown')}")
            return parsed
        
        # Try JSON parsing first (for JSON documents)
        try:
            logger.debug(f"DEBUG: _parse_doc_content - attempting JSON parse: {content[:200]}...")
            
            parsed = json.loads(content_stripped)
            logger.debug(f"DEBUG: _parse_doc_content - JSON parsed result: {parsed}")
            
            # Merge with metadata to ensure we have all information (metadata takes precedence for conflicts)
            if isinstance(parsed, dict):
                # Add enriched metadata if available
                if metadata.get("query_patterns"):
                    parsed["query_patterns"] = metadata.get("query_patterns")
                if metadata.get("use_cases"):
                    parsed["use_cases"] = metadata.get("use_cases")
                # Preserve columns from metadata if they exist and aren't in parsed content
                if "columns" not in parsed and "columns" in metadata:
                    parsed["columns"] = metadata.get("columns", [])
                # Merge other metadata fields that might not be in parsed content
                for key, value in metadata.items():
                    if key not in parsed or not parsed[key]:
                        parsed[key] = value
            
            return parsed
        except json.JSONDecodeError:
            # Fall back to ast.literal_eval for Python literals
            try:
                # Skip empty strings to avoid syntax errors
                if not content_stripped:
                    logger.debug("Empty content after stripping, building from metadata")
                    parsed = {}
                    # Copy all metadata fields
                    for key, value in metadata.items():
                        parsed[key] = value
                    # Ensure essential fields
                    if "type" not in parsed:
                        parsed["type"] = metadata.get("type", "")
                    if "name" not in parsed:
                        parsed["name"] = metadata.get("name", "")
                    if "table_name" not in parsed:
                        parsed["table_name"] = metadata.get("table_name", "")
                    if "mdl_type" not in parsed:
                        parsed["mdl_type"] = metadata.get("mdl_type", "")
                    if "relationships" not in parsed:
                        parsed["relationships"] = metadata.get("relationships", [])
                    if "columns" not in parsed and "columns" in metadata:
                        parsed["columns"] = metadata.get("columns", [])
                    return parsed
                
                parsed = ast.literal_eval(content_stripped)
                logger.debug(f"DEBUG: _parse_doc_content - ast parsed result: {parsed}")
                
                # Add enriched metadata if available and merge with parsed content
                if isinstance(parsed, dict):
                    if metadata.get("query_patterns"):
                        parsed["query_patterns"] = metadata.get("query_patterns")
                    if metadata.get("use_cases"):
                        parsed["use_cases"] = metadata.get("use_cases")
                    # Preserve columns from metadata if they exist and aren't in parsed content
                    if "columns" not in parsed and "columns" in metadata:
                        parsed["columns"] = metadata.get("columns", [])
                    # Merge other metadata fields
                    for key, value in metadata.items():
                        if key not in parsed or not parsed[key]:
                            parsed[key] = value
                
                return parsed
            except (ValueError, SyntaxError) as e:
                logger.warning(f"Failed to parse content with ast.literal_eval: {content[:200]}... | Error: {str(e)}")
                # Fallback to metadata-based dict - preserve all column information
                parsed = {}
                # Copy all metadata fields to preserve all information including columns
                for key, value in metadata.items():
                    parsed[key] = value
                # Ensure essential fields
                if "type" not in parsed:
                    parsed["type"] = metadata.get("type", "")
                if "name" not in parsed:
                    parsed["name"] = metadata.get("name", "")
                if "table_name" not in parsed:
                    parsed["table_name"] = metadata.get("table_name", "")
                if "description" not in parsed and content_stripped:
                    parsed["description"] = content_stripped
                if "mdl_type" not in parsed:
                    parsed["mdl_type"] = metadata.get("mdl_type", "")
                if "relationships" not in parsed:
                    parsed["relationships"] = metadata.get("relationships", [])
                # Ensure columns are preserved - CRITICAL
                if "columns" in metadata:
                    columns_value = metadata.get("columns", [])
                    parsed["columns"] = columns_value
                    logger.debug(f"DEBUG: _parse_doc_content - preserved {len(columns_value) if isinstance(columns_value, list) else 'N/A'} columns from metadata in exception fallback")
                else:
                    logger.warning(f"DEBUG: _parse_doc_content - NO COLUMNS in metadata for {parsed.get('name', 'unknown')} in exception fallback")
                logger.debug(f"DEBUG: _parse_doc_content - exception fallback to metadata: {parsed.get('name', 'unknown')}")
                return parsed
        except Exception as e:
            logger.warning(f"Failed to parse content: {content[:200]}... | Error: {str(e)}")
            # Fallback to metadata-based dict - preserve all column information
            parsed = {}
            # Copy all metadata fields to preserve all information including columns
            for key, value in metadata.items():
                parsed[key] = value
            # Ensure essential fields are set
            if "type" not in parsed:
                parsed["type"] = metadata.get("type", "")
            if "name" not in parsed:
                parsed["name"] = metadata.get("name", "")
            if "table_name" not in parsed:
                parsed["table_name"] = metadata.get("table_name", "")
            if "description" not in parsed:
                parsed["description"] = metadata.get("description", "")
            if "mdl_type" not in parsed:
                parsed["mdl_type"] = metadata.get("mdl_type", "")
            if "relationships" not in parsed:
                parsed["relationships"] = metadata.get("relationships", [])
            # Preserve columns if they exist in metadata
            if "columns" not in parsed and "columns" in metadata:
                parsed["columns"] = metadata.get("columns", [])
            logger.debug(f"DEBUG: _parse_doc_content - exception fallback to metadata: {parsed.get('name', 'unknown')}")
            return parsed
    
    async def search_db_schema(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[MDLSchemaResult]:
        """Search leen_db_schema collection for database schemas."""
        cache_key = self._get_cache_key("search_db_schema", query, limit, project_id)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self._db_schema_store:
                logger.warning("leen_db_schema store not available")
                return []
            
            where = None
            if project_id:
                where = {"project_id": {"$eq": project_id}}
            
            results = self._db_schema_store.semantic_search(
                query=query,
                k=limit,
                where=where
            )
            
            formatted_results = []
            for i, result in enumerate(results):
                try:
                    # Use the same parsing logic as retrieval.py
                    content_dict = self._parse_doc_content(result)
                    
                    # Log raw result structure for debugging (first 3 only)
                    if i < 3:
                        logger.info(f"  Raw Qdrant result [{i+1}]:")
                        logger.info(f"    metadata keys: {list(result.get('metadata', {}).keys())}")
                        logger.info(f"    metadata full: {json.dumps(result.get('metadata', {}), default=str, indent=2)}")
                        logger.info(f"    parsed content_dict keys: {list(content_dict.keys())}")
                        logger.info(f"    parsed content_dict sample: {json.dumps({k: str(v)[:200] if not isinstance(v, (dict, list)) else type(v).__name__ for k, v in list(content_dict.items())[:10]}, default=str)}")
                    
                    # Extract table name from parsed content_dict (which includes metadata)
                    table_name = (
                        content_dict.get("name") or
                        content_dict.get("table_name") or
                        result.get("metadata", {}).get("name") or
                        result.get("metadata", {}).get("table_name") or
                        ""
                    )
                    
                    if not table_name and i < 3:
                        logger.warning(f"    ⚠ Could not extract table_name from result [{i+1}]")
                        logger.warning(f"      Tried: content_dict['name']={content_dict.get('name')}, content_dict['table_name']={content_dict.get('table_name')}, metadata['name']={result.get('metadata', {}).get('name')}")
                    
                    # Extract schema DDL and columns from parsed content
                    schema_ddl = content_dict.get("ddl", "") or content_dict.get("schema_ddl", "")
                    columns = content_dict.get("columns", [])
                    
                    schema_result = MDLSchemaResult(
                        table_name=table_name or "unknown",
                        schema_ddl=schema_ddl,
                        columns=columns if isinstance(columns, list) else [],
                        metadata=result.get("metadata", {}),
                        score=result.get("score", 0.0),
                        id=result.get("id", "")
                    )
                    formatted_results.append(schema_result)
                except Exception as e:
                    logger.warning(f"Error processing schema result [{i+1}]: {e}")
                    continue
            
            if formatted_results:
                await self._cache.set(cache_key, formatted_results, ttl=300)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching db_schema: {e}", exc_info=True)
            return []
    
    async def search_table_descriptions(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[MDLTableDescriptionResult]:
        """Search leen_table_description collection for table descriptions."""
        cache_key = self._get_cache_key("search_table_descriptions", query, limit, project_id)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self._table_desc_store:
                logger.warning("leen_table_description store not available")
                return []
            
            where = None
            if project_id:
                where = {"project_id": {"$eq": project_id}}
            
            results = self._table_desc_store.semantic_search(
                query=query,
                k=limit,
                where=where
            )
            
            formatted_results = []
            for i, result in enumerate(results):
                try:
                    # Use the same parsing logic as retrieval.py
                    content_dict = self._parse_doc_content(result)
                    
                    # Log raw result structure for debugging (first 3 only)
                    if i < 3:
                        logger.info(f"  Raw Qdrant table_description result [{i+1}]:")
                        logger.info(f"    metadata keys: {list(result.get('metadata', {}).keys())}")
                        logger.info(f"    metadata full: {json.dumps(result.get('metadata', {}), default=str, indent=2)}")
                        logger.info(f"    parsed content_dict keys: {list(content_dict.keys())}")
                        logger.info(f"    parsed content_dict sample: {json.dumps({k: str(v)[:200] if not isinstance(v, (dict, list)) else type(v).__name__ for k, v in list(content_dict.items())[:10]}, default=str)}")
                    
                    # Extract table name from parsed content_dict (which includes metadata)
                    table_name = (
                        content_dict.get("name") or
                        content_dict.get("table_name") or
                        result.get("metadata", {}).get("name") or
                        result.get("metadata", {}).get("table_name") or
                        ""
                    )
                    
                    if not table_name and i < 3:
                        logger.warning(f"    ⚠ Could not extract table_name from table_description result [{i+1}]")
                        logger.warning(f"      Tried: content_dict['name']={content_dict.get('name')}, content_dict['table_name']={content_dict.get('table_name')}, metadata['name']={result.get('metadata', {}).get('name')}")
                    
                    # Extract description and relationships from parsed content
                    description = content_dict.get("description", "")
                    relationships = content_dict.get("relationships", [])
                    
                    table_result = MDLTableDescriptionResult(
                        table_name=table_name or "unknown",
                        description=description,
                        relationships=relationships if isinstance(relationships, list) else [],
                        metadata=result.get("metadata", {}),
                        score=result.get("score", 0.0),
                        id=result.get("id", "")
                    )
                    formatted_results.append(table_result)
                except Exception as e:
                    logger.warning(f"Error processing table_description result [{i+1}]: {e}")
                    continue
            
            if formatted_results:
                await self._cache.set(cache_key, formatted_results, ttl=300)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching table_descriptions: {e}", exc_info=True)
            return []
    
    async def search_project_meta(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[MDLProjectMetaResult]:
        """Search leen_project_meta collection for project metadata."""
        cache_key = self._get_cache_key("search_project_meta", query, limit, project_id)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self._project_meta_store:
                logger.warning("leen_project_meta store not available")
                return []
            
            where = None
            if project_id:
                where = {"project_id": {"$eq": project_id}}
            
            results = self._project_meta_store.semantic_search(
                query=query,
                k=limit,
                where=where
            )
            
            formatted_results = []
            for result in results:
                formatted = self._format_result(result, "project_meta")
                if formatted:
                    content = formatted.get("content", {}) if isinstance(formatted.get("content"), dict) else {}
                    metadata = formatted["metadata"]
                    
                    project_result = MDLProjectMetaResult(
                        project_id=metadata.get("project_id", "") or content.get("project_id", ""),
                        project_name=metadata.get("project_name", "") or content.get("project_name", ""),
                        metadata=metadata,
                        content=str(formatted.get("content", "")),
                        score=formatted["score"],
                        id=formatted["id"]
                    )
                    formatted_results.append(project_result)
            
            if formatted_results:
                await self._cache.set(cache_key, formatted_results, ttl=300)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching project_meta: {e}", exc_info=True)
            return []
    
    async def search_metrics_registry(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[MDLMetricResult]:
        """Search leen_metrics_registry collection for metrics/KPIs."""
        cache_key = self._get_cache_key("search_metrics_registry", query, limit, project_id)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self._metrics_store:
                logger.warning("leen_metrics_registry store not available")
                return []
            
            where = None
            if project_id:
                where = {"project_id": {"$eq": project_id}}
            
            results = self._metrics_store.semantic_search(
                query=query,
                k=limit,
                where=where
            )
            
            formatted_results = []
            for result in results:
                formatted = self._format_result(result, "metric")
                if formatted:
                    content = formatted.get("content", {}) if isinstance(formatted.get("content"), dict) else {}
                    metadata = formatted["metadata"]
                    
                    # Merge content fields into metadata for easier access
                    # This allows filtering logic to access source_capabilities, category, etc.
                    merged_metadata = {**metadata}
                    if isinstance(content, dict):
                        # Merge content fields into metadata (content takes precedence)
                        for key in ["source_capabilities", "category", "source_schemas", "kpis", 
                                   "trends", "natural_language_question", "data_filters", 
                                   "data_groups", "data_capability", "id", "name", "description",
                                   "metric_id", "transformation_layer"]:
                            if key in content:
                                merged_metadata[key] = content[key]
                    
                    metric_result = MDLMetricResult(
                        metric_name=metadata.get("metric_name", "") or content.get("name", ""),
                        metric_definition=content.get("description", "") or content.get("definition", "") or metadata.get("definition", ""),
                        kpi_type=content.get("kpi_type", "") or metadata.get("kpi_type"),
                        thresholds=content.get("thresholds", {}) or metadata.get("thresholds", {}),
                        metadata=merged_metadata,  # Use merged metadata
                        score=formatted["score"],
                        id=formatted["id"] or content.get("id", "")
                    )
                    formatted_results.append(metric_result)
            
            if formatted_results:
                await self._cache.set(cache_key, formatted_results, ttl=300)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching metrics_registry: {e}", exc_info=True)
            return []
    
    async def search_dashboard_patterns(
        self,
        query: str,
        limit: int = 10,
        component_type: Optional[str] = None,
        data_domain: Optional[str] = None,
    ) -> List[MDLDashboardPatternResult]:
        """
        Search mdl_dashboards collection for reference dashboard component patterns.
        
        Cross-project retrieval: does NOT filter by project_id. Patterns from any 
        project are valid few-shot examples for generating dashboards on new 
        data sources or topics.
        
        Args:
            query: Semantic search query (user's dashboard request)
            limit: Max results
            component_type: Optional filter (kpi/metric/table/insight) for post-retrieval filtering
            data_domain: Optional domain filter for post-retrieval re-ranking
        
        Returns:
            List of component-level pattern dicts with parent dashboard context
        """
        cache_key = self._get_cache_key("search_dashboard_patterns", query, limit, component_type, data_domain)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self._dashboard_store:
                logger.warning("mdl_dashboards store not available")
                return []
            
            # NO project_id filter — cross-project few-shot retrieval
            # This is intentional: patterns from any project are valid examples
            where = None
            
            results = self._dashboard_store.semantic_search(
                query=query,
                k=limit * 2 if component_type or data_domain else limit,  # Get more for filtering
                where=where
            )
            
            formatted_results = []
            for result in results:
                try:
                    formatted = self._format_result(result, "dashboard_pattern")
                    if not formatted:
                        continue
                    
                    content = formatted.get("content", {}) if isinstance(formatted.get("content"), dict) else {}
                    metadata = formatted["metadata"]
                    
                    # Merge content fields into metadata
                    merged_metadata = {**metadata}
                    if isinstance(content, dict):
                        for key in ["question", "component_type", "data_tables", "reasoning", 
                                   "chart_hint", "columns_used", "filters_available", 
                                   "dashboard_name", "dashboard_description", "dashboard_id",
                                   "project_id", "source_id", "component_sequence", "sql_query",
                                   "tags"]:
                            if key in content:
                                merged_metadata[key] = content[key]
                    
                    # Post-filter by component_type if specified
                    if component_type:
                        pattern_type = merged_metadata.get("component_type", "")
                        if pattern_type != component_type:
                            continue
                    
                    # Post-filter by data_domain if specified (re-ranking)
                    if data_domain:
                        pattern_domain = merged_metadata.get("metadata", {}).get("data_domain") or merged_metadata.get("data_domain")
                        if pattern_domain and pattern_domain != data_domain:
                            # Lower score for domain mismatch (but still include)
                            formatted["score"] = formatted["score"] * 0.8
                    
                    dashboard_result = MDLDashboardPatternResult(
                        question=merged_metadata.get("question", ""),
                        component_type=merged_metadata.get("component_type", ""),
                        data_tables=merged_metadata.get("data_tables", []),
                        reasoning=merged_metadata.get("reasoning", ""),
                        chart_hint=merged_metadata.get("chart_hint"),
                        columns_used=merged_metadata.get("columns_used", []),
                        filters_available=merged_metadata.get("filters_available", []),
                        dashboard_name=merged_metadata.get("dashboard_name"),
                        dashboard_description=merged_metadata.get("dashboard_description"),
                        dashboard_id=merged_metadata.get("dashboard_id"),
                        project_id=merged_metadata.get("project_id"),
                        source_id=merged_metadata.get("source_id"),
                        component_sequence=merged_metadata.get("component_sequence"),
                        sql_query=merged_metadata.get("sql_query"),
                        tags=merged_metadata.get("tags", []),
                        metadata=merged_metadata,
                        score=formatted["score"],
                        id=formatted["id"]
                    )
                    formatted_results.append(dashboard_result)
                    
                    # Stop if we have enough after filtering
                    if len(formatted_results) >= limit:
                        break
                
                except Exception as e:
                    logger.warning(f"Error processing dashboard pattern result: {e}")
                    continue
            
            # Sort by score descending
            formatted_results.sort(key=lambda x: x.score, reverse=True)
            
            if formatted_results:
                await self._cache.set(cache_key, formatted_results, ttl=300)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching dashboard_patterns: {e}", exc_info=True)
            return []
    
    async def search_all_mdl(
        self,
        query: str,
        limit_per_collection: int = 3,
        project_id: Optional[str] = None
    ) -> MDLRetrievedContext:
        """
        Search all MDL collections simultaneously and merge results.
        
        Args:
            query: Natural language query
            limit_per_collection: Max results per collection
            project_id: Optional project ID filter
            
        Returns:
            MDLRetrievedContext with results from all collections
        """
        # Search all collections in parallel (using async)
        import asyncio
        
        tasks = [
            self.search_db_schema(query, limit_per_collection, project_id),
            self.search_table_descriptions(query, limit_per_collection, project_id),
            self.search_project_meta(query, limit_per_collection, project_id),
            self.search_metrics_registry(query, limit_per_collection, project_id),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions gracefully
        db_schemas = results[0] if not isinstance(results[0], Exception) else []
        table_descriptions = results[1] if not isinstance(results[1], Exception) else []
        project_meta = results[2] if not isinstance(results[2], Exception) else []
        metrics = results[3] if not isinstance(results[3], Exception) else []
        
        # Log exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                collection_names = ["db_schema", "table_descriptions", "project_meta", "metrics_registry"]
                logger.error(f"Error searching {collection_names[i]}: {result}")
        
        return MDLRetrievedContext(
            query=query,
            db_schemas=db_schemas if isinstance(db_schemas, list) else [],
            table_descriptions=table_descriptions if isinstance(table_descriptions, list) else [],
            project_meta=project_meta if isinstance(project_meta, list) else [],
            metrics=metrics if isinstance(metrics, list) else [],
            total_hits=0  # Will be calculated in __post_init__
        )
