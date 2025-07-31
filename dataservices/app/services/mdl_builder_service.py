"""
MDL Builder Service
Builds MDL (Model Definition Language) definitions from PostgreSQL objects
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.schemas.dbmodels import (
    Domain, Dataset, Table, SQLColumn, Metric, View, 
    CalculatedColumn, SQLFunction, Relationship
)
from app.service.models import DomainContext

logger = logging.getLogger(__name__)


class MDLBuilderService:
    """Service for building MDL definitions from PostgreSQL objects"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def build_domain_mdl(
        self, 
        domain_id: str, 
        db: AsyncSession,
        include_llm_definitions: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete MDL definition for a domain
        
        Args:
            domain_id: ID of the domain
            db: Database session
            include_llm_definitions: Whether to include LLM-generated definitions
            
        Returns:
            Complete MDL definition dictionary
        """
        self.logger.info(f"Building MDL for domain {domain_id}")
        
        try:
            # Get domain with all related data
            domain = await self._get_domain_with_details(domain_id, db)
            if not domain:
                raise ValueError(f"Domain {domain_id} not found")
            
            # Build base MDL structure
            mdl = {
                "domain_id": domain.domain_id,
                "domain_name": domain.display_name,
                "description": domain.description,
                "version": domain.version_string,
                "status": domain.status,
                "created_at": domain.created_at.isoformat() if domain.created_at else None,
                "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
                "created_by": domain.created_by,
                "last_modified_by": domain.last_modified_by,
                "generated_at": datetime.utcnow().isoformat(),
                "mdl_version": "1.0",
                "metadata": {
                    "business_domain": domain.json_metadata.get("context", {}).get("business_domain", "General"),
                    "target_users": domain.json_metadata.get("context", {}).get("target_users", ["Data Analysts"]),
                    "key_concepts": domain.json_metadata.get("context", {}).get("key_business_concepts", []),
                    "domain_type": "data_domain",
                    "total_tables": len(domain.tables) if domain.tables else 0,
                    "total_metrics": sum(len(table.metrics) for table in domain.tables) if domain.tables else 0,
                    "total_views": sum(len(table.views) for table in domain.tables) if domain.tables else 0,
                    "total_calculated_columns": sum(
                        len([col for col in table.columns if col.calculated_column]) 
                        for table in domain.tables
                    ) if domain.tables else 0
                }
            }
            
            # Build tables section
            mdl["tables"] = await self._build_tables_mdl(domain, db, include_llm_definitions)
            
            # Build metrics section
            mdl["metrics"] = await self._build_metrics_mdl(domain, db, include_llm_definitions)
            
            # Build views section
            mdl["views"] = await self._build_views_mdl(domain, db, include_llm_definitions)
            
            # Build calculated columns section
            mdl["calculated_columns"] = await self._build_calculated_columns_mdl(domain, db, include_llm_definitions)
            
            # Build functions section
            mdl["functions"] = await self._build_functions_mdl(domain, db)
            
            # Build relationships section
            mdl["relationships"] = await self._build_relationships_mdl(domain, db)
            
            # Build enums section (if any)
            mdl["enums"] = await self._build_enums_mdl(domain, db)
            
            # Add LLM definitions if available and requested
            if include_llm_definitions and domain.json_metadata:
                llm_definitions = domain.json_metadata.get("llm_definitions", {})
                if llm_definitions:
                    mdl["llm_definitions"] = llm_definitions
            
            self.logger.info(f"Successfully built MDL for domain {domain_id}")
            return mdl
            
        except Exception as e:
            self.logger.error(f"Error building MDL for domain {domain_id}: {str(e)}")
            raise
    
    async def _get_domain_with_details(self, domain_id: str, db: AsyncSession) -> Optional[Domain]:
        """Get domain with all related details"""
        result = await db.execute(
            select(Domain)
            .options(
                selectinload(Domain.tables)
                .selectinload(Table.columns)
                .selectinload(SQLColumn.calculated_column),
                selectinload(Domain.tables)
                .selectinload(Table.metrics),
                selectinload(Domain.tables)
                .selectinload(Table.views),
                selectinload(Domain.sql_functions),
                selectinload(Domain.relationships),
                selectinload(Domain.datasets)
            )
            .where(Domain.domain_id == domain_id)
        )
        return result.scalar_one_or_none()
    
    async def _build_tables_mdl(
        self, 
        domain: Domain, 
        db: AsyncSession,
        include_llm_definitions: bool = True
    ) -> List[Dict[str, Any]]:
        """Build tables section of MDL"""
        tables_mdl = []
        
        for table in domain.tables:
            table_mdl = {
                "table_id": table.table_id,
                "name": table.name,
                "display_name": table.display_name,
                "description": table.description,
                "table_type": table.table_type,
                "dataset_id": table.dataset_id,
                "dataset_name": table.dataset.name if table.dataset else None,
                "created_at": table.created_at.isoformat() if table.created_at else None,
                "updated_at": table.updated_at.isoformat() if table.updated_at else None,
                "entity_version": table.entity_version,
                "columns": [],
                "metadata": table.json_metadata or {}
            }
            
            # Add LLM definitions if available
            if include_llm_definitions and table.json_metadata:
                llm_data = table.json_metadata.get("llm_definitions", {})
                if llm_data:
                    table_mdl.update({
                        "business_purpose": llm_data.get("business_purpose"),
                        "primary_use_cases": llm_data.get("primary_use_cases", []),
                        "key_relationships": llm_data.get("key_relationships", []),
                        "data_lineage": llm_data.get("data_lineage"),
                        "update_frequency": llm_data.get("update_frequency"),
                        "data_retention": llm_data.get("data_retention"),
                        "access_patterns": llm_data.get("access_patterns", []),
                        "performance_considerations": llm_data.get("performance_considerations", [])
                    })
            
            # Build columns
            for column in table.columns:
                column_mdl = await self._build_column_mdl(column, include_llm_definitions)
                table_mdl["columns"].append(column_mdl)
            
            tables_mdl.append(table_mdl)
        
        return tables_mdl
    
    async def _build_column_mdl(
        self, 
        column: SQLColumn,
        include_llm_definitions: bool = True
    ) -> Dict[str, Any]:
        """Build column definition for MDL"""
        column_mdl = {
            "column_id": column.column_id,
            "name": column.name,
            "display_name": column.display_name,
            "description": column.description,
            "column_type": column.column_type,
            "data_type": column.data_type,
            "usage_type": column.usage_type,
            "is_nullable": column.is_nullable,
            "is_primary_key": column.is_primary_key,
            "is_foreign_key": column.is_foreign_key,
            "default_value": column.default_value,
            "ordinal_position": column.ordinal_position,
            "created_at": column.created_at.isoformat() if column.created_at else None,
            "updated_at": column.updated_at.isoformat() if column.updated_at else None,
            "entity_version": column.entity_version,
            "metadata": column.json_metadata or {}
        }
        
        # Add calculated column information if applicable
        if column.calculated_column:
            column_mdl["calculated_column"] = {
                "calculated_column_id": column.calculated_column.calculated_column_id,
                "calculation_sql": column.calculated_column.calculation_sql,
                "function_id": column.calculated_column.function_id,
                "dependencies": column.calculated_column.dependencies or []
            }
        
        # Add LLM definitions if available
        if include_llm_definitions and column.json_metadata:
            llm_data = column.json_metadata.get("llm_definitions", {})
            if llm_data:
                column_mdl.update({
                    "business_description": llm_data.get("business_description"),
                    "example_values": llm_data.get("example_values", []),
                    "business_rules": llm_data.get("business_rules", []),
                    "data_quality_checks": llm_data.get("data_quality_checks", []),
                    "related_concepts": llm_data.get("related_concepts", []),
                    "privacy_classification": llm_data.get("privacy_classification"),
                    "aggregation_suggestions": llm_data.get("aggregation_suggestions", []),
                    "filtering_suggestions": llm_data.get("filtering_suggestions", [])
                })
        
        return column_mdl
    
    async def _build_metrics_mdl(
        self, 
        domain: Domain, 
        db: AsyncSession,
        include_llm_definitions: bool = True
    ) -> List[Dict[str, Any]]:
        """Build metrics section of MDL"""
        metrics_mdl = []
        
        for table in domain.tables:
            for metric in table.metrics:
                metric_mdl = {
                    "metric_id": metric.metric_id,
                    "name": metric.name,
                    "display_name": metric.display_name,
                    "description": metric.description,
                    "table_id": metric.table_id,
                    "table_name": table.name,
                    "metric_sql": metric.metric_sql,
                    "metric_type": metric.metric_type,
                    "aggregation_type": metric.aggregation_type,
                    "format_string": metric.format_string,
                    "created_at": metric.created_at.isoformat() if metric.created_at else None,
                    "updated_at": metric.updated_at.isoformat() if metric.updated_at else None,
                    "entity_version": metric.entity_version,
                    "metadata": metric.json_metadata or {}
                }
                
                # Add LLM definitions if available
                if include_llm_definitions and metric.json_metadata:
                    llm_data = metric.json_metadata.get("llm_definitions", {})
                    if llm_data:
                        metric_mdl.update({
                            "business_purpose": llm_data.get("business_purpose"),
                            "calculation_logic": llm_data.get("calculation_logic"),
                            "business_rules": llm_data.get("business_rules", []),
                            "interpretation_guidelines": llm_data.get("interpretation_guidelines", []),
                            "related_metrics": llm_data.get("related_metrics", []),
                            "alert_thresholds": llm_data.get("alert_thresholds", [])
                        })
                
                metrics_mdl.append(metric_mdl)
        
        return metrics_mdl
    
    async def _build_views_mdl(
        self, 
        domain: Domain, 
        db: AsyncSession,
        include_llm_definitions: bool = True
    ) -> List[Dict[str, Any]]:
        """Build views section of MDL"""
        views_mdl = []
        
        for table in domain.tables:
            for view in table.views:
                view_mdl = {
                    "view_id": view.view_id,
                    "name": view.name,
                    "display_name": view.display_name,
                    "description": view.description,
                    "table_id": view.table_id,
                    "table_name": table.name,
                    "view_sql": view.view_sql,
                    "view_type": view.view_type,
                    "created_at": view.created_at.isoformat() if view.created_at else None,
                    "updated_at": view.updated_at.isoformat() if view.updated_at else None,
                    "entity_version": view.entity_version,
                    "metadata": view.json_metadata or {}
                }
                
                # Add LLM definitions if available
                if include_llm_definitions and view.json_metadata:
                    llm_data = view.json_metadata.get("llm_definitions", {})
                    if llm_data:
                        view_mdl.update({
                            "business_purpose": llm_data.get("business_purpose"),
                            "use_cases": llm_data.get("use_cases", []),
                            "data_sources": llm_data.get("data_sources", []),
                            "refresh_frequency": llm_data.get("refresh_frequency"),
                            "access_patterns": llm_data.get("access_patterns", [])
                        })
                
                views_mdl.append(view_mdl)
        
        return views_mdl
    
    async def _build_calculated_columns_mdl(
        self, 
        domain: Domain, 
        db: AsyncSession,
        include_llm_definitions: bool = True
    ) -> List[Dict[str, Any]]:
        """Build calculated columns section of MDL"""
        calculated_columns_mdl = []
        
        for table in domain.tables:
            for column in table.columns:
                if column.calculated_column:
                    calc_column_mdl = {
                        "calculated_column_id": column.calculated_column.calculated_column_id,
                        "column_id": column.column_id,
                        "column_name": column.name,
                        "table_id": table.table_id,
                        "table_name": table.name,
                        "calculation_sql": column.calculated_column.calculation_sql,
                        "function_id": column.calculated_column.function_id,
                        "dependencies": column.calculated_column.dependencies or [],
                        "created_at": column.calculated_column.created_at.isoformat() if column.calculated_column.created_at else None,
                        "updated_at": column.calculated_column.updated_at.isoformat() if column.calculated_column.updated_at else None,
                        "entity_version": column.calculated_column.entity_version,
                        "metadata": column.calculated_column.json_metadata or {}
                    }
                    
                    # Add LLM definitions if available
                    if include_llm_definitions and column.json_metadata:
                        llm_data = column.json_metadata.get("llm_definitions", {})
                        if llm_data:
                            calc_column_mdl.update({
                                "business_purpose": llm_data.get("business_purpose"),
                                "calculation_logic": llm_data.get("calculation_logic"),
                                "business_rules": llm_data.get("business_rules", []),
                                "dependencies_explanation": llm_data.get("dependencies_explanation", [])
                            })
                    
                    calculated_columns_mdl.append(calc_column_mdl)
        
        return calculated_columns_mdl
    
    async def _build_functions_mdl(self, domain: Domain, db: AsyncSession) -> List[Dict[str, Any]]:
        """Build functions section of MDL"""
        functions_mdl = []
        
        for function in domain.sql_functions:
            function_mdl = {
                "function_id": function.function_id,
                "name": function.name,
                "display_name": function.display_name,
                "description": function.description,
                "function_sql": function.function_sql,
                "return_type": function.return_type,
                "parameters": function.parameters or [],
                "created_at": function.created_at.isoformat() if function.created_at else None,
                "updated_at": function.updated_at.isoformat() if function.updated_at else None,
                "entity_version": function.entity_version,
                "metadata": function.json_metadata or {}
            }
            
            functions_mdl.append(function_mdl)
        
        return functions_mdl
    
    async def _build_relationships_mdl(self, domain: Domain, db: AsyncSession) -> List[Dict[str, Any]]:
        """Build relationships section of MDL"""
        relationships_mdl = []
        
        for relationship in domain.relationships:
            relationship_mdl = {
                "relationship_id": relationship.relationship_id,
                "name": relationship.name,
                "relationship_type": relationship.relationship_type,
                "from_table_id": relationship.from_table_id,
                "to_table_id": relationship.to_table_id,
                "from_column_id": relationship.from_column_id,
                "to_column_id": relationship.to_column_id,
                "description": relationship.description,
                "is_active": relationship.is_active,
                "created_at": relationship.created_at.isoformat() if relationship.created_at else None,
                "updated_at": relationship.updated_at.isoformat() if relationship.updated_at else None,
                "entity_version": relationship.entity_version,
                "metadata": relationship.json_metadata or {}
            }
            
            # Add table and column names for easier reference
            if relationship.from_table:
                relationship_mdl["from_table_name"] = relationship.from_table.name
            if relationship.to_table:
                relationship_mdl["to_table_name"] = relationship.to_table.name
            if relationship.from_column:
                relationship_mdl["from_column_name"] = relationship.from_column.name
            if relationship.to_column:
                relationship_mdl["to_column_name"] = relationship.to_column.name
            
            relationships_mdl.append(relationship_mdl)
        
        return relationships_mdl
    
    async def _build_enums_mdl(self, domain: Domain, db: AsyncSession) -> List[Dict[str, Any]]:
        """Build enums section of MDL (placeholder for future enum support)"""
        # Currently, the database models don't include enum definitions
        # This is a placeholder for future enum support
        enums_mdl = []
        
        # Extract potential enum values from column metadata
        for table in domain.tables:
            for column in table.columns:
                if column.json_metadata and column.json_metadata.get("enum_values"):
                    enum_mdl = {
                        "enum_name": f"{table.name}_{column.name}_enum",
                        "table_name": table.name,
                        "column_name": column.name,
                        "values": column.json_metadata.get("enum_values", []),
                        "description": f"Enum values for {table.name}.{column.name}",
                        "metadata": column.json_metadata.get("enum_metadata", {})
                    }
                    enums_mdl.append(enum_mdl)
        
        return enums_mdl
    
    async def build_table_mdl(
        self, 
        table_id: str, 
        db: AsyncSession,
        include_llm_definitions: bool = True
    ) -> Dict[str, Any]:
        """
        Build MDL definition for a single table
        
        Args:
            table_id: ID of the table
            db: Database session
            include_llm_definitions: Whether to include LLM-generated definitions
            
        Returns:
            Table MDL definition dictionary
        """
        self.logger.info(f"Building MDL for table {table_id}")
        
        try:
            # Get table with all related data
            result = await db.execute(
                select(Table)
                .options(
                    selectinload(Table.columns)
                    .selectinload(SQLColumn.calculated_column),
                    selectinload(Table.metrics),
                    selectinload(Table.views),
                    selectinload(Table.domain),
                    selectinload(Table.dataset)
                )
                .where(Table.table_id == table_id)
            )
            table = result.scalar_one_or_none()
            
            if not table:
                raise ValueError(f"Table {table_id} not found")
            
            # Build table MDL
            table_mdl = {
                "table_id": table.table_id,
                "name": table.name,
                "display_name": table.display_name,
                "description": table.description,
                "table_type": table.table_type,
                "domain_id": table.domain_id,
                "domain_name": table.domain.display_name if table.domain else None,
                "dataset_id": table.dataset_id,
                "dataset_name": table.dataset.name if table.dataset else None,
                "created_at": table.created_at.isoformat() if table.created_at else None,
                "updated_at": table.updated_at.isoformat() if table.updated_at else None,
                "entity_version": table.entity_version,
                "columns": [],
                "metrics": [],
                "views": [],
                "metadata": table.json_metadata or {}
            }
            
            # Add LLM definitions if available
            if include_llm_definitions and table.json_metadata:
                llm_data = table.json_metadata.get("llm_definitions", {})
                if llm_data:
                    table_mdl.update({
                        "business_purpose": llm_data.get("business_purpose"),
                        "primary_use_cases": llm_data.get("primary_use_cases", []),
                        "key_relationships": llm_data.get("key_relationships", []),
                        "data_lineage": llm_data.get("data_lineage"),
                        "update_frequency": llm_data.get("update_frequency"),
                        "data_retention": llm_data.get("data_retention"),
                        "access_patterns": llm_data.get("access_patterns", []),
                        "performance_considerations": llm_data.get("performance_considerations", [])
                    })
            
            # Build columns
            for column in table.columns:
                column_mdl = await self._build_column_mdl(column, include_llm_definitions)
                table_mdl["columns"].append(column_mdl)
            
            # Build metrics
            for metric in table.metrics:
                metric_mdl = {
                    "metric_id": metric.metric_id,
                    "name": metric.name,
                    "display_name": metric.display_name,
                    "description": metric.description,
                    "metric_sql": metric.metric_sql,
                    "metric_type": metric.metric_type,
                    "aggregation_type": metric.aggregation_type,
                    "format_string": metric.format_string,
                    "created_at": metric.created_at.isoformat() if metric.created_at else None,
                    "updated_at": metric.updated_at.isoformat() if metric.updated_at else None,
                    "entity_version": metric.entity_version,
                    "metadata": metric.json_metadata or {}
                }
                
                # Add LLM definitions if available
                if include_llm_definitions and metric.json_metadata:
                    llm_data = metric.json_metadata.get("llm_definitions", {})
                    if llm_data:
                        metric_mdl.update({
                            "business_purpose": llm_data.get("business_purpose"),
                            "calculation_logic": llm_data.get("calculation_logic"),
                            "business_rules": llm_data.get("business_rules", []),
                            "interpretation_guidelines": llm_data.get("interpretation_guidelines", []),
                            "related_metrics": llm_data.get("related_metrics", []),
                            "alert_thresholds": llm_data.get("alert_thresholds", [])
                        })
                
                table_mdl["metrics"].append(metric_mdl)
            
            # Build views
            for view in table.views:
                view_mdl = {
                    "view_id": view.view_id,
                    "name": view.name,
                    "display_name": view.display_name,
                    "description": view.description,
                    "view_sql": view.view_sql,
                    "view_type": view.view_type,
                    "created_at": view.created_at.isoformat() if view.created_at else None,
                    "updated_at": view.updated_at.isoformat() if view.updated_at else None,
                    "entity_version": view.entity_version,
                    "metadata": view.json_metadata or {}
                }
                
                # Add LLM definitions if available
                if include_llm_definitions and view.json_metadata:
                    llm_data = view.json_metadata.get("llm_definitions", {})
                    if llm_data:
                        view_mdl.update({
                            "business_purpose": llm_data.get("business_purpose"),
                            "use_cases": llm_data.get("use_cases", []),
                            "data_sources": llm_data.get("data_sources", []),
                            "refresh_frequency": llm_data.get("refresh_frequency"),
                            "access_patterns": llm_data.get("access_patterns", [])
                        })
                
                table_mdl["views"].append(view_mdl)
            
            self.logger.info(f"Successfully built MDL for table {table_id}")
            return table_mdl
            
        except Exception as e:
            self.logger.error(f"Error building MDL for table {table_id}: {str(e)}")
            raise
    
    async def save_mdl_to_file(
        self, 
        mdl_data: Dict[str, Any], 
        file_path: str
    ) -> Dict[str, Any]:
        """
        Save MDL data to a JSON file
        
        Args:
            mdl_data: MDL definition dictionary
            file_path: Path to save the file
            
        Returns:
            Dictionary with file information
        """
        try:
            import json
            import os
            from pathlib import Path
            
            # Create directory if it doesn't exist
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Write MDL file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(mdl_data, f, indent=2, ensure_ascii=False)
            
            # Get file stats
            file_size = file_path_obj.stat().st_size
            
            result = {
                "success": True,
                "file_path": str(file_path),
                "file_size": file_size,
                "domain_id": mdl_data.get("domain_id"),
                "generated_at": mdl_data.get("generated_at")
            }
            
            self.logger.info(f"MDL file saved: {file_path} ({file_size} bytes)")
            return result
            
        except Exception as e:
            self.logger.error(f"Error saving MDL file {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }


# Global instance
mdl_builder_service = MDLBuilderService() 