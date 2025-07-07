# unstructured/genieml/dataservices/app/services/project_workflow_service.py

from typing import Dict, Optional, Any, List
from uuid import uuid4
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, func
from pydantic import BaseModel, Field, ConfigDict
import asyncpg
from app.service.models import ProjectCreate, TableCreate, ColumnCreate, MetricCreate, ViewCreate, CalculatedColumnCreate, ProjectResponse, TableResponse
from app.schemas.dbmodels import Project, Table, SQLColumn, Metric, View, CalculatedColumn, Dataset
from app.agents.schema_manager import LLMSchemaDocumentationGenerator
from app.service.models import ProjectContext, SchemaInput, AddTableRequest
import os
from app.utils.cache import get_cache_provider
from app.utils.sse import publish_update
from app.core.dependencies import get_llm

logger = logging.getLogger(__name__)

class ProjectWorkflowService:
    def __init__(self, user_id: str, session_id: Optional[str] = None, llm=None):
        self.user_id = user_id
        self.session_id = session_id
        self.cache = get_cache_provider()
        #self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.llm = get_llm()
        self.definition_manager = LLMSchemaDocumentationGenerator(self.llm)

    def _workflow_cache_key(self) -> str:
        if self.session_id:
            return f"project_workflow:{self.user_id}:{self.session_id}"
        return f"project_workflow:{self.user_id}"

    def get_workflow_state(self) -> dict:
        state = self.cache.get(self._workflow_cache_key())
        if state is None:
            state = {"project": None, "context": None, "datasets": [], "tables": []}
            self.cache.set(self._workflow_cache_key(), state)
        return state

    def set_workflow_state(self, state: dict):
        self.cache.set(self._workflow_cache_key(), state)

    async def create_project(self, project_data: dict):
        state = self.get_workflow_state()
        state["project"] = project_data  # or Project(**project_data)
        self.set_workflow_state(state)
        publish_update(self.user_id, self.session_id or "default", state)
        return state["project"]
    
    async def add_dataset(self, dataset_data: dict):
        state = self.get_workflow_state()
        state["datasets"].append(dataset_data)
        self.set_workflow_state(state)
        publish_update(self.user_id, self.session_id or "default", state)
        return state["datasets"]
    
    async def get_semantic_description_for_table(self, add_table_request: AddTableRequest, project_context: ProjectContext) -> Dict[str, Any]:
        """Generate semantic description for a table using the semantics description service"""
        try:
            from app.agents.semantics_description import SemanticsDescription
            
            schema_input = add_table_request.schema
            
            # Convert schema input to table data format expected by semantics service
            table_data = {
                "name": schema_input.table_name,
                "display_name": schema_input.table_name,
                "description": schema_input.table_description or f"Table for {schema_input.table_name}",
                "columns": []
            }
            
            # Convert columns from schema input to the expected format
            for col in schema_input.columns:
                column_data = {
                    "name": col.get("name", "unknown"),
                    "display_name": col.get("display_name") or col.get("name", "unknown"),
                    "description": col.get("description"),
                    "data_type": col.get("data_type"),
                    "is_primary_key": col.get("is_primary_key", False),
                    "is_nullable": col.get("is_nullable", True),
                    "usage_type": col.get("usage_type")
                }
                table_data["columns"].append(column_data)
            
            # Create semantics description service instance
            semantics_service = SemanticsDescription()
            
            # Generate description
            result = await semantics_service.describe(
                SemanticsDescription.Input(
                    id=f"workflow_table_{schema_input.table_name}_{project_context.project_id}",
                    table_data=table_data,
                    project_id=project_context.project_id
                )
            )
            
            if result.status == "finished" and result.response:
                # Return the full response
                return result.response
            else:
                logger.error(f"Failed to generate semantic description for table {schema_input.table_name}: {result.error}")
                # Return fallback response
                return {
                    "description": f"Semantic description for {schema_input.table_name}: This table contains {schema_input.table_description or 'data related to the business domain'}. Generated automatically based on table structure and content.",
                    "table_purpose": f"Stores {schema_input.table_description or 'data'} for {schema_input.table_name}",
                    "key_columns": [],
                    "business_context": f"This table supports the {project_context.business_domain} domain by storing {schema_input.table_description or 'relevant data'}.",
                    "data_patterns": ["Data storage", "Information management"],
                    "suggested_relationships": []
                }
                
        except Exception as e:
            logger.error(f"Error generating semantic description for table {schema_input.table_name}: {str(e)}")
            # Return fallback response
            return {
                "description": f"Semantic description for {schema_input.table_name}: This table contains {schema_input.table_description or 'data related to the business domain'}. Generated automatically based on table structure and content.",
                "table_purpose": f"Stores {schema_input.table_description or 'data'} for {schema_input.table_name}",
                "key_columns": [],
                "business_context": f"This table supports the {project_context.business_domain} domain by storing {schema_input.table_description or 'relevant data'}.",
                "data_patterns": ["Data storage", "Information management"],
                "suggested_relationships": []
            }
        
    async def get_relationship_recommendation_for_table(self, add_table_request: AddTableRequest, project_context: ProjectContext) -> Dict[str, Any]:
        """Generate relationship recommendations for a table using the relationship recommendation service"""
        try:
            from app.agents.relationship_recommendation import RelationshipRecommendation
            
            schema_input = add_table_request.schema
            
            # Convert schema input to table data format expected by relationship service
            table_data = {
                "name": schema_input.table_name,
                "display_name": schema_input.table_name,
                "description": schema_input.table_description or f"Table for {schema_input.table_name}",
                "columns": []
            }
            
            # Convert columns from schema input to the expected format
            for col in schema_input.columns:
                column_data = {
                    "name": col.get("name", "unknown"),
                    "display_name": col.get("display_name") or col.get("name", "unknown"),
                    "description": col.get("description"),
                    "data_type": col.get("data_type"),
                    "is_primary_key": col.get("is_primary_key", False),
                    "is_nullable": col.get("is_nullable", True),
                    "is_foreign_key": col.get("is_foreign_key", False),
                    "usage_type": col.get("usage_type")
                }
                table_data["columns"].append(column_data)
            
            # Create relationship recommendation service instance
            relationship_service = RelationshipRecommendation()
            
            # Generate recommendations
            result = await relationship_service.recommend(
                RelationshipRecommendation.Input(
                    id=f"workflow_relationships_{schema_input.table_name}_{project_context.project_id}",
                    table_data=table_data,
                    project_id=project_context.project_id
                )
            )
            
            if result.status == "finished" and result.response:
                # Return the full response
                return result.response
            else:
                logger.error(f"Failed to generate relationship recommendations for table {schema_input.table_name}: {result.error}")
                # Return fallback response
                return {
                    "relationships": [],
                    "summary": {
                        "total_relationships": 0,
                        "primary_relationships": [],
                        "recommendations": [
                            f"Consider adding foreign key relationships for {schema_input.table_name}",
                            "Review table structure for potential normalization opportunities"
                        ]
                    }
                }
                
        except Exception as e:
            logger.error(f"Error generating relationship recommendations for table {schema_input.table_name}: {str(e)}")
            # Return fallback response
            return {
                "relationships": [],
                "summary": {
                    "total_relationships": 0,
                    "primary_relationships": [],
                    "recommendations": [
                        f"Consider adding foreign key relationships for {schema_input.table_name}",
                        "Review table structure for potential normalization opportunities",
                        f"Error during analysis: {str(e)}"
                    ]
                }
            }

    async def get_recommendations(self, add_table_request: AddTableRequest, project_context: ProjectContext, recommendation_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate comprehensive recommendations for a table including semantic descriptions and relationships
        
        Args:
            add_table_request: The table request containing schema information
            project_context: The project context for business domain understanding
            recommendation_types: List of recommendation types to generate. 
                                Defaults to ["semantic", "relationships", "optimization"]
        
        Returns:
            Dictionary containing all requested recommendations
        """
        if recommendation_types is None:
            recommendation_types = ["semantic", "relationships", "optimization"]
        
        recommendations = {
            "table_name": add_table_request.schema.table_name,
            "project_id": project_context.project_id,
            "generated_at": datetime.now().isoformat(),
            "recommendation_types": recommendation_types,
            "results": {}
        }
        
        try:
            # Generate semantic description if requested
            if "semantic" in recommendation_types:
                logger.info(f"Generating semantic description for table {add_table_request.schema.table_name}")
                semantic_description = await self.get_semantic_description_for_table(add_table_request, project_context)
                recommendations["results"]["semantic_description"] = semantic_description
            
            # Generate relationship recommendations if requested
            if "relationships" in recommendation_types:
                logger.info(f"Generating relationship recommendations for table {add_table_request.schema.table_name}")
                relationship_recommendations = await self.get_relationship_recommendation_for_table(add_table_request, project_context)
                recommendations["results"]["relationship_recommendations"] = relationship_recommendations
            
            # Generate optimization recommendations if requested
            if "optimization" in recommendation_types:
                logger.info(f"Generating optimization recommendations for table {add_table_request.schema.table_name}")
                optimization_recommendations = await self._generate_optimization_recommendations(add_table_request, project_context)
                recommendations["results"]["optimization_recommendations"] = optimization_recommendations
            
            # Generate data quality recommendations if requested
            if "data_quality" in recommendation_types:
                logger.info(f"Generating data quality recommendations for table {add_table_request.schema.table_name}")
                data_quality_recommendations = await self._generate_data_quality_recommendations(add_table_request, project_context)
                recommendations["results"]["data_quality_recommendations"] = data_quality_recommendations
            
            # Generate summary and overall recommendations
            recommendations["summary"] = await self._generate_recommendations_summary(recommendations["results"])
            
            logger.info(f"Successfully generated {len(recommendation_types)} types of recommendations for table {add_table_request.schema.table_name}")
            
        except Exception as e:
            logger.error(f"Error generating recommendations for table {add_table_request.schema.table_name}: {str(e)}")
            recommendations["error"] = str(e)
            recommendations["status"] = "failed"
        
        return recommendations

    async def _generate_optimization_recommendations(self, add_table_request: AddTableRequest, project_context: ProjectContext) -> Dict[str, Any]:
        """Generate optimization recommendations for table structure and performance"""
        schema_input = add_table_request.schema
        
        recommendations = {
            "performance_optimizations": [],
            "structure_improvements": [],
            "indexing_suggestions": [],
            "partitioning_recommendations": []
        }
        
        # Analyze columns for optimization opportunities
        for col in schema_input.columns:
            col_name = col.get("name", "")
            data_type = col.get("data_type", "")
            is_primary_key = col.get("is_primary_key", False)
            is_foreign_key = col.get("is_foreign_key", False)
            
            # Performance optimization suggestions
            if is_foreign_key:
                recommendations["indexing_suggestions"].append({
                    "column": col_name,
                    "recommendation": f"Add index on {col_name} for foreign key relationship",
                    "priority": "high",
                    "impact": "Query performance improvement"
                })
            
            if data_type and "VARCHAR" in data_type.upper():
                # Check for potential length optimization
                if "255" in data_type:
                    recommendations["structure_improvements"].append({
                        "column": col_name,
                        "recommendation": f"Consider optimizing VARCHAR length for {col_name}",
                        "priority": "medium",
                        "impact": "Storage optimization"
                    })
            
            if data_type and "TIMESTAMP" in data_type.upper():
                recommendations["performance_optimizations"].append({
                    "column": col_name,
                    "recommendation": f"Consider partitioning by {col_name} for time-series data",
                    "priority": "medium",
                    "impact": "Query performance for time-based queries"
                })
        
        # General recommendations based on table structure
        if len(schema_input.columns) > 20:
            recommendations["structure_improvements"].append({
                "column": "table_structure",
                "recommendation": "Consider normalizing table with many columns",
                "priority": "medium",
                "impact": "Maintainability and performance"
            })
        
        return recommendations

    async def _generate_data_quality_recommendations(self, add_table_request: AddTableRequest, project_context: ProjectContext) -> Dict[str, Any]:
        """Generate data quality recommendations for table"""
        schema_input = add_table_request.schema
        
        recommendations = {
            "constraint_suggestions": [],
            "validation_rules": [],
            "monitoring_recommendations": []
        }
        
        # Analyze columns for data quality improvements
        for col in schema_input.columns:
            col_name = col.get("name", "")
            data_type = col.get("data_type", "")
            is_nullable = col.get("is_nullable", True)
            is_primary_key = col.get("is_primary_key", False)
            
            # Constraint suggestions
            if not is_nullable and not is_primary_key:
                recommendations["constraint_suggestions"].append({
                    "column": col_name,
                    "recommendation": f"Add NOT NULL constraint to {col_name}",
                    "priority": "high",
                    "impact": "Data integrity"
                })
            
            # Data type specific validations
            if data_type and "EMAIL" in col_name.upper():
                recommendations["validation_rules"].append({
                    "column": col_name,
                    "rule": "Email format validation",
                    "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                    "priority": "high"
                })
            
            if data_type and "PHONE" in col_name.upper():
                recommendations["validation_rules"].append({
                    "column": col_name,
                    "rule": "Phone number format validation",
                    "pattern": r"^\+?[\d\s\-\(\)]+$",
                    "priority": "medium"
                })
            
            if data_type and "URL" in col_name.upper():
                recommendations["validation_rules"].append({
                    "column": col_name,
                    "rule": "URL format validation",
                    "pattern": r"^https?://[^\s/$.?#].[^\s]*$",
                    "priority": "medium"
                })
        
        # General monitoring recommendations
        recommendations["monitoring_recommendations"] = [
            {
                "type": "duplicate_detection",
                "recommendation": "Implement duplicate detection for key columns",
                "priority": "medium"
            },
            {
                "type": "completeness_check",
                "recommendation": "Monitor data completeness for required fields",
                "priority": "high"
            },
            {
                "type": "consistency_check",
                "recommendation": "Validate data consistency across related tables",
                "priority": "medium"
            }
        ]
        
        return recommendations

    async def _generate_recommendations_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of all recommendations"""
        summary = {
            "total_recommendations": 0,
            "high_priority_items": [],
            "medium_priority_items": [],
            "low_priority_items": [],
            "key_insights": [],
            "next_steps": []
        }
        
        # Count recommendations from different sources
        if "relationship_recommendations" in results:
            rel_recs = results["relationship_recommendations"]
            summary["total_recommendations"] += len(rel_recs.get("relationships", []))
            
            # Add high-priority relationship recommendations
            for rel in rel_recs.get("relationships", []):
                if rel.get("confidence_score", 0) > 0.8:
                    summary["high_priority_items"].append({
                        "type": "relationship",
                        "description": f"High-confidence relationship: {rel.get('source_table')} → {rel.get('target_table')}",
                        "confidence": rel.get("confidence_score")
                    })
        
        if "optimization_recommendations" in results:
            opt_recs = results["optimization_recommendations"]
            
            # Count optimization recommendations
            for category in ["performance_optimizations", "structure_improvements", "indexing_suggestions"]:
                summary["total_recommendations"] += len(opt_recs.get(category, []))
                
                for rec in opt_recs.get(category, []):
                    priority = rec.get("priority", "medium")
                    if priority == "high":
                        summary["high_priority_items"].append({
                            "type": "optimization",
                            "description": rec.get("recommendation", ""),
                            "impact": rec.get("impact", "")
                        })
        
        if "data_quality_recommendations" in results:
            dq_recs = results["data_quality_recommendations"]
            
            # Count data quality recommendations
            for category in ["constraint_suggestions", "validation_rules", "monitoring_recommendations"]:
                summary["total_recommendations"] += len(dq_recs.get(category, []))
                
                for rec in dq_recs.get(category, []):
                    priority = rec.get("priority", "medium")
                    if priority == "high":
                        summary["high_priority_items"].append({
                            "type": "data_quality",
                            "description": rec.get("recommendation", "") or rec.get("rule", ""),
                            "impact": "Data integrity improvement"
                        })
        
        # Generate key insights
        if summary["high_priority_items"]:
            summary["key_insights"].append(f"Found {len(summary['high_priority_items'])} high-priority recommendations")
        
        if "relationship_recommendations" in results:
            rel_count = len(results["relationship_recommendations"].get("relationships", []))
            if rel_count > 0:
                summary["key_insights"].append(f"Identified {rel_count} potential table relationships")
        
        # Generate next steps
        if summary["high_priority_items"]:
            summary["next_steps"].append("Review and implement high-priority recommendations")
        
        if "relationship_recommendations" in results:
            summary["next_steps"].append("Consider implementing suggested table relationships")
        
        if "optimization_recommendations" in results:
            summary["next_steps"].append("Apply performance optimizations for better query performance")
        
        return summary

    async def add_table(self, add_table_request: AddTableRequest, project_context: ProjectContext):
        state = self.get_workflow_state()
        schema_input = add_table_request.schema
        
        # Generate semantic description first
        semantic_description = await self.get_semantic_description_for_table(add_table_request, project_context)
        
        # Generate relationship recommendations
        relationship_recommendations = await self.get_relationship_recommendation_for_table(add_table_request, project_context)
        
        table = Table(
            name=schema_input.table_name,
            display_name=schema_input.table_name,
            description=schema_input.table_description,
            dataset_id=add_table_request.dataset_id,
            metadata={
                "columns": schema_input.columns,
                "semantic_description": semantic_description.get("description", ""),
                "semantic_analysis": semantic_description,
                "relationship_recommendations": relationship_recommendations
            }
        )
        
        # LLM Table Definition (enhanced with semantic description)
        
        documented_table = await self.definition_manager.document_table_schema(schema_input, project_context)
        
        # Attach LLM output to table (customize as needed)
        table.description = documented_table.description
        
        # Add semantic description and relationship recommendations to the documented table
        documented_table.semantic_description = semantic_description
        documented_table.relationship_recommendations = relationship_recommendations
        
        state["tables"].append(table)
        self.set_workflow_state(state)
        publish_update(self.user_id, self.session_id or "default", state)
        return documented_table

    async def commit_workflow(self, db_session):
        """Commit the workflow state to database and clean up cache"""
        state = self.get_workflow_state()
        project_data = state.get("project")
        if not project_data:
            raise ValueError("No project defined in workflow state.")
        
        # The actual database operations are now handled in the router
        # This method just cleans up the workflow state
        self.cache.delete(self._workflow_cache_key())
        publish_update(self.user_id, self.session_id or "default", {
            "status": "committed", 
            "project": project_data.get("project_id"),
            "message": "Workflow committed successfully"
        })
        return state
    

class MetricsService:
    """Service for managing metrics, views, and calculated columns using LLMDefinitionGenerator"""
    
    def __init__(self, db: AsyncSession, project_id: str = None):
        self.db = db
        self.project_id = project_id
        # Initialize LLM Definition Generator
        from app.agents.project_manager import LLMDefinitionGenerator
        self.llm_generator = LLMDefinitionGenerator()
    
    async def _get_project_context(self, table_id: str) -> Dict[str, Any]:
        """Get project context for LLM definition generation"""
        try:
            # Get table and its project
            from sqlalchemy import select
            table = await self.db.execute(
                select(Table).where(Table.table_id == table_id)
            )
            table = table.scalar_one_or_none()
            
            if not table:
                raise ValueError(f"Table {table_id} not found")
            
            project_id = table.project_id
            
            # Get all tables in the project
            tables = await self.db.execute(
                select(Table).where(Table.project_id == project_id)
            )
            tables = tables.scalars().all()
            
            # Build table context
            table_context = {}
            for t in tables:
                table_info = {
                    "name": t.name,
                    "display_name": t.display_name or t.name,
                    "description": t.description or "",
                    "columns": []
                }
                
                # Get columns for this table
                columns = await self.db.execute(
                    select(SQLColumn).where(SQLColumn.table_id == t.table_id)
                )
                columns = columns.scalars().all()
                
                for col in columns:
                    table_info["columns"].append({
                        "name": col.name,
                        "display_name": col.display_name or col.name,
                        "data_type": col.data_type,
                        "description": col.description or "",
                        "usage_type": col.usage_type
                    })
                
                table_context[t.name] = table_info
            
            # Get existing metrics
            existing_metrics = {}
            for t in tables:
                metrics = await self.db.execute(
                    select(Metric).where(Metric.table_id == t.table_id)
                )
                metrics = metrics.scalars().all()
                
                for metric in metrics:
                    existing_metrics[metric.name] = metric.description or ""
            
            # Get project metadata for business context
            project = await self.db.execute(
                select(Project).where(Project.project_id == project_id)
            )
            project = project.scalar_one_or_none()
            
            business_context = {}
            if project and project.json_metadata:
                business_context = project.json_metadata.get("business_context", {})
            
            return {
                "tables": table_context,
                "existing_metrics": existing_metrics,
                "business_context": business_context,
                "data_lineage": {}  # Could be enhanced with actual lineage data
            }
            
        except Exception as e:
            logger.error(f"Error getting project context: {str(e)}")
            return {
                "tables": {},
                "existing_metrics": {},
                "business_context": {},
                "data_lineage": {}
            }
    
    async def add_metric(self, table_id: str, metric_data: MetricCreate, created_by: str) -> Metric:
        """Add metric to table using LLMDefinitionGenerator for enhancement"""
        try:
            # Get project context
            context = await self._get_project_context(table_id)
            
            # Create UserExample for LLM generation
            from app.service.models import UserExample, DefinitionType
            user_example = UserExample(
                definition_type=DefinitionType.METRIC,
                name=metric_data.name,
                description=metric_data.description or f"Metric for {metric_data.name}",
                sql=metric_data.metric_sql,
                additional_context={
                    "metric_type": metric_data.metric_type,
                    "aggregation_type": metric_data.aggregation_type,
                    "business_purpose": metric_data.description
                },
                user_id=created_by
            )
            
            # Generate enhanced definition using LLM
            enhanced_definition = await self.llm_generator.generate_metric_definition(user_example, context)
            
            # Create metric with enhanced data
            metric = Metric(
                table_id=table_id,
                name=enhanced_definition.name,
                display_name=enhanced_definition.display_name,
                description=enhanced_definition.description,
                metric_sql=enhanced_definition.sql_query,
                metric_type=enhanced_definition.metadata.get("metric_type", metric_data.metric_type),
                aggregation_type=enhanced_definition.metadata.get("aggregation_type", metric_data.aggregation_type),
                format_string=enhanced_definition.metadata.get("format_string"),
                modified_by=created_by,
                json_metadata={
                    **enhanced_definition.metadata,
                    "chain_of_thought": enhanced_definition.chain_of_thought,
                    "confidence_score": enhanced_definition.confidence_score,
                    "suggestions": enhanced_definition.suggestions,
                    "related_tables": enhanced_definition.related_tables,
                    "related_columns": enhanced_definition.related_columns,
                    "generated_by": "llm_definition_generator",
                    "original_data": {
                        "name": metric_data.name,
                        "description": metric_data.description,
                        "metric_sql": metric_data.metric_sql,
                        "metric_type": metric_data.metric_type,
                        "aggregation_type": metric_data.aggregation_type
                    }
                }
            )
            
            self.db.add(metric)
            await self.db.commit()
            await self.db.refresh(metric)
            
            logger.info(f"Created enhanced metric '{metric.name}' with LLM-generated improvements")
            return metric
            
        except Exception as e:
            logger.error(f"Error creating enhanced metric: {str(e)}")
            # Fallback to original method if LLM generation fails
            metric = Metric(
                table_id=table_id,
                name=metric_data.name,
                display_name=metric_data.display_name or metric_data.name,
                description=metric_data.description,
                metric_sql=metric_data.metric_sql,
                metric_type=metric_data.metric_type,
                aggregation_type=metric_data.aggregation_type,
                modified_by=created_by
            )
            
            self.db.add(metric)
            await self.db.commit()
            await self.db.refresh(metric)
            return metric
    
    async def add_view(self, table_id: str, view_data: ViewCreate, created_by: str) -> View:
        """Add view to table using LLMDefinitionGenerator for enhancement"""
        try:
            # Get project context
            context = await self._get_project_context(table_id)
            
            # Create UserExample for LLM generation
            from app.service.models import UserExample, DefinitionType
            user_example = UserExample(
                definition_type=DefinitionType.VIEW,
                name=view_data.name,
                description=view_data.description or f"View for {view_data.name}",
                sql=view_data.view_sql,
                additional_context={
                    "view_type": view_data.view_type,
                    "business_purpose": view_data.description,
                    "target_audience": "business_analysts"
                },
                user_id=created_by
            )
            
            # Generate enhanced definition using LLM
            enhanced_definition = await self.llm_generator.generate_view_definition(user_example, context)
            
            # Create view with enhanced data
            view = View(
                table_id=table_id,
                name=enhanced_definition.name,
                display_name=enhanced_definition.display_name,
                description=enhanced_definition.description,
                view_sql=enhanced_definition.sql_query,
                view_type=enhanced_definition.metadata.get("view_type", view_data.view_type),
                modified_by=created_by,
                json_metadata={
                    **enhanced_definition.metadata,
                    "chain_of_thought": enhanced_definition.chain_of_thought,
                    "confidence_score": enhanced_definition.confidence_score,
                    "suggestions": enhanced_definition.suggestions,
                    "related_tables": enhanced_definition.related_tables,
                    "related_columns": enhanced_definition.related_columns,
                    "generated_by": "llm_definition_generator",
                    "original_data": {
                        "name": view_data.name,
                        "description": view_data.description,
                        "view_sql": view_data.view_sql,
                        "view_type": view_data.view_type
                    }
                }
            )
            
            self.db.add(view)
            await self.db.commit()
            await self.db.refresh(view)
            
            logger.info(f"Created enhanced view '{view.name}' with LLM-generated improvements")
            return view
            
        except Exception as e:
            logger.error(f"Error creating enhanced view: {str(e)}")
            # Fallback to original method if LLM generation fails
            view = View(
                table_id=table_id,
                name=view_data.name,
                display_name=view_data.display_name or view_data.name,
                description=view_data.description,
                view_sql=view_data.view_sql,
                view_type=view_data.view_type,
                modified_by=created_by
            )
            
            self.db.add(view)
            await self.db.commit()
            await self.db.refresh(view)
            return view
    
    async def add_calculated_column(self, table_id: str, column_data: dict, created_by: str) -> SQLColumn:
        """Add calculated column using LLMDefinitionGenerator for enhancement"""
        try:
            # Get project context
            context = await self._get_project_context(table_id)
            
            # Create UserExample for LLM generation
            from app.service.models import UserExample, DefinitionType
            user_example = UserExample(
                definition_type=DefinitionType.CALCULATED_COLUMN,
                name=column_data.get("name"),
                description=column_data.get("description") or f"Calculated column {column_data.get('name')}",
                sql=column_data.get("calculation_sql"),
                additional_context={
                    "data_type": column_data.get("data_type"),
                    "usage_type": column_data.get("usage_type"),
                    "dependencies": column_data.get("dependencies", []),
                    "business_purpose": column_data.get("description")
                },
                user_id=created_by
            )
            
            # Generate enhanced definition using LLM
            enhanced_definition = await self.llm_generator.generate_calculated_column_definition(user_example, context)
            
            # Create SQLColumn with enhanced data
            column = SQLColumn(
                table_id=table_id,
                name=enhanced_definition.name,
                display_name=enhanced_definition.display_name,
                description=enhanced_definition.description,
                column_type='calculated_column',  # Mark as calculated column
                data_type=enhanced_definition.metadata.get("data_type", column_data.get("data_type")),
                usage_type=enhanced_definition.metadata.get("calculation_type", column_data.get("usage_type")),
                is_nullable=column_data.get("is_nullable", True),
                is_primary_key=column_data.get("is_primary_key", False),
                is_foreign_key=column_data.get("is_foreign_key", False),
                default_value=column_data.get("default_value"),
                ordinal_position=column_data.get("ordinal_position"),
                json_metadata={
                    **enhanced_definition.metadata,
                    "chain_of_thought": enhanced_definition.chain_of_thought,
                    "confidence_score": enhanced_definition.confidence_score,
                    "suggestions": enhanced_definition.suggestions,
                    "related_tables": enhanced_definition.related_tables,
                    "related_columns": enhanced_definition.related_columns,
                    "generated_by": "llm_definition_generator",
                    "original_data": column_data
                },
                modified_by=created_by
            )
            
            self.db.add(column)
            await self.db.commit()
            await self.db.refresh(column)
            
            # Create the associated CalculatedColumn with enhanced calculation details
            calc_column = CalculatedColumn(
                column_id=column.column_id,
                calculation_sql=enhanced_definition.sql_query,
                function_id=column_data.get("function_id"),
                dependencies=enhanced_definition.metadata.get("dependencies", column_data.get("dependencies", [])),
                modified_by=created_by
            )
            
            self.db.add(calc_column)
            await self.db.commit()
            await self.db.refresh(calc_column)
            
            logger.info(f"Created enhanced calculated column '{column.name}' with LLM-generated improvements")
            return column
            
        except Exception as e:
            logger.error(f"Error creating enhanced calculated column: {str(e)}")
            # Fallback to original method if LLM generation fails
            column = SQLColumn(
                table_id=table_id,
                name=column_data.get("name"),
                display_name=column_data.get("display_name") or column_data.get("name"),
                description=column_data.get("description"),
                column_type='calculated_column',  # Mark as calculated column
                data_type=column_data.get("data_type"),
                usage_type=column_data.get("usage_type"),
                is_nullable=column_data.get("is_nullable", True),
                is_primary_key=column_data.get("is_primary_key", False),
                is_foreign_key=column_data.get("is_foreign_key", False),
                default_value=column_data.get("default_value"),
                ordinal_position=column_data.get("ordinal_position"),
                json_metadata=column_data.get("metadata", {}),
                modified_by=created_by
            )
            
            self.db.add(column)
            await self.db.commit()
            await self.db.refresh(column)
            
            # Then create the associated CalculatedColumn with the calculation details
            calc_column = CalculatedColumn(
                column_id=column.column_id,
                calculation_sql=column_data.get("calculation_sql"),
                function_id=column_data.get("function_id"),
                dependencies=column_data.get("dependencies", []),
                modified_by=created_by
            )
            
            self.db.add(calc_column)
            await self.db.commit()
            await self.db.refresh(calc_column)
            
            return column