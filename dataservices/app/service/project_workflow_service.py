# unstructured/genieml/dataservices/app/services/domain_workflow_service.py

from typing import Dict, Optional, Any, List
from uuid import uuid4
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, func

from app.service.models import MetricCreate, ViewCreate, SchemaInput
from app.schemas.dbmodels import Domain, Table, SQLColumn, Metric, View, CalculatedColumn, Relationship
from app.agents.schema_manager import LLMSchemaDocumentationGenerator
from app.service.models import DomainContext, AddTableRequest
import os
from app.utils.cache import get_cache_provider
from app.utils.sse import publish_update
from app.core.dependencies import get_llm
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class DomainWorkflowService:
    def __init__(self, user_id: str, session_id: Optional[str] = None, llm=None):
        self.user_id = user_id
        self.session_id = session_id
        self.cache = get_cache_provider()
        #self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.llm = get_llm()
        self.definition_manager = LLMSchemaDocumentationGenerator(self.llm)
        # Initialize sharing permissions service
        try:
            from app.service.sharing_permissions_service import SharingPermissionsService
            self.sharing_service = SharingPermissionsService()
        except ImportError:
            logger.warning("SharingPermissionsService not available, sharing permissions will be skipped")
            self.sharing_service = None

    def _workflow_cache_key(self) -> str:
        if self.session_id:
            return f"domain_workflow:{self.user_id}:{self.session_id}"
        return f"domain_workflow:{self.user_id}"

    def get_workflow_state(self) -> dict:
        state = self.cache.get(self._workflow_cache_key())
        if state is None:
            state = {"domain": None, "context": None, "datasets": [], "tables": [], "relationships": []}
            self.cache.set(self._workflow_cache_key(), state)
        return state

    def set_workflow_state(self, state: dict):
        self.cache.set(self._workflow_cache_key(), state)

    async def create_domain(self, domain_data: dict):
        state = self.get_workflow_state()
        state["domain"] = domain_data  # or Domain(**domain_data)
        self.set_workflow_state(state)
        publish_update(self.user_id, self.session_id or "default", state)
        return state["domain"]
    
    async def add_dataset(self, dataset_data: dict):
        state = self.get_workflow_state()
        state["datasets"].append(dataset_data)
        self.set_workflow_state(state)
        publish_update(self.user_id, self.session_id or "default", state)
        return state["datasets"]
    
    async def fetch_and_store_sharing_permissions(self, domain_id: str) -> Dict[str, Any]:
        """
        Fetch sharing permissions from team API and store them in the domain metadata
        
        This method is called after dataset creation to establish sharing permissions
        for the domain/project.
        
        Args:
            domain_id: The ID of the domain to store permissions for
            
        Returns:
            Dictionary containing the stored permissions data
        """
        try:
            if not self.sharing_service:
                logger.warning("Sharing permissions service not available, skipping permissions fetch")
                return {"status": "skipped", "reason": "Service not available"}
            
            logger.info(f"Fetching sharing permissions for domain {domain_id}")
            
            # Fetch permissions from team API
            permissions_data = await self.sharing_service.fetch_sharing_permissions(self.user_id)
            
            # Store permissions in domain metadata
            stored_permissions = await self.sharing_service.store_permissions_in_project(domain_id, permissions_data)
            
            # Update workflow state with permissions
            state = self.get_workflow_state()
            state["sharing_permissions"] = stored_permissions
            self.set_workflow_state(state)
            
            # Publish update
            publish_update(self.user_id, self.session_id or "default", {
                "type": "sharing_permissions_fetched",
                "data": stored_permissions
            })
            
            logger.info(f"Successfully fetched and stored sharing permissions for domain {domain_id}")
            return stored_permissions
            
        except Exception as e:
            logger.error(f"Error fetching sharing permissions for domain {domain_id}: {str(e)}")
            # Return error response but don't fail the workflow
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to fetch sharing permissions"
            }
    
    async def get_semantic_description_for_table(self, add_table_request: AddTableRequest, domain_context: DomainContext) -> Dict[str, Any]:
        """Generate semantic description for a table using the semantics description service"""
        try:
            try:
                from app.agents.semantics_description import SemanticsDescription
            except Exception as import_error:
                import traceback
                traceback.print_exc()
                raise import_error
            
            
            
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
                    id=f"workflow_table_{schema_input.table_name}_{domain_context.domain_id}",
                    table_data=table_data,
                    domain_id=domain_context.domain_id
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
                    "business_context": f"This table supports the {domain_context.business_domain} domain by storing {schema_input.table_description or 'relevant data'}.",
                    "data_patterns": ["Data storage", "Information management"],
                    "suggested_relationships": []
                }
                
        except Exception as e:
            logger.error(f"Error generating semantic description for table {schema_input.table_name}: {str(e)}")
            # Return fallback response
            return {
                "description": f"Semantic description for {schema_input.table_name}: This table contains {schema_input.table_description or 'data related to the business domain'}. Generated automatically based on table structure and content.",
                "table_purpose": f"Stores {schema_input.table_description or 'data'} for {schema_input.table_name}",
                "business_context": f"This table supports the {domain_context.business_domain} domain by storing {schema_input.table_description or 'relevant data'}.",
                "data_patterns": ["Data storage", "Information management"],
                "suggested_relationships": []
            }
        
    async def get_relationship_recommendation_for_table(self, add_table_request: AddTableRequest, domain_context: DomainContext) -> Dict[str, Any]:
        """Generate relationship recommendations for a table using the relationship recommendation service"""
        try:
            try:
                from app.agents.relationship_recommendation import RelationshipRecommendation
            except Exception as import_error:
                import traceback
                traceback.print_exc()
                raise import_error
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
                    id=f"workflow_relationships_{schema_input.table_name}_{domain_context.domain_id}",
                    table_data=table_data,
                    domain_id=domain_context.domain_id
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

    async def get_comprehensive_relationship_recommendations(self, domain_context: DomainContext) -> Dict[str, Any]:
        """
        Generate comprehensive relationship recommendations for all tables in the domain workflow
        
        This method uses the existing RelationshipRecommendation service to analyze all tables
        in the workflow and generate relationship recommendations between them.
        
        Args:
            domain_context: The domain context for business domain understanding
        
        Returns:
            Dictionary containing relationship recommendations for all tables
        """
        try:
            state = self.get_workflow_state()
            tables = state.get("tables", [])
            
            if not tables:
                return {
                    "status": "no_tables",
                    "message": "No tables have been added to the workflow yet. Add tables first to get relationship recommendations.",
                    "recommendations": [],
                    "summary": {
                        "total_tables": 0,
                        "total_relationships": 0,
                        "recommendations": ["Add tables to the workflow to begin relationship analysis"]
                    }
                }
            
            logger.info(f"Generating relationship recommendations for {len(tables)} tables in domain {domain_context.domain_id}")
            
            # Import the existing RelationshipRecommendation service
            try:
                from app.agents.relationship_recommendation import RelationshipRecommendation
            except ImportError:
                logger.error("RelationshipRecommendation service not available")
                return {
                    "status": "error",
                    "error": "RelationshipRecommendation service not available",
                    "message": "Failed to import relationship recommendation service"
                }
            
            # Build MDL representation from workflow tables
            mdl_data = self._build_mdl_from_workflow_tables(tables, domain_context)
            
            # Create relationship recommendation service instance
            relationship_service = RelationshipRecommendation()
            
            # Generate recommendations using existing service
            result = await relationship_service.recommend(
                RelationshipRecommendation.Input(
                    id=f"workflow_relationships_{domain_context.domain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    mdl=mdl_data,
                    project_id=domain_context.domain_id
                )
            )
            
            if result.status == "finished" and result.response:
                # Process the response from the existing service
                recommendations = self._process_relationship_recommendations(
                    result.response, tables, domain_context
                )
                
                # Store recommendations in workflow state
                state["relationship_recommendations"] = recommendations
                self.set_workflow_state(state)
                
                # Publish update
                publish_update(self.user_id, self.session_id or "default", {
                    "type": "relationship_recommendations_generated",
                    "data": recommendations
                })
                
                logger.info(f"Successfully generated relationship recommendations for {len(tables)} tables")
                return recommendations
            else:
                logger.error(f"Failed to generate relationship recommendations: {result.error}")
                return {
                    "status": "error",
                    "error": str(result.error) if result.error else "Unknown error",
                    "message": "Failed to generate relationship recommendations using existing service"
                }
            
        except Exception as e:
            logger.error(f"Error generating comprehensive relationship recommendations: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to generate relationship recommendations",
                "recommendations": [],
                "summary": {
                    "total_relationships": 0,
                    "recommendations": [f"Error during analysis: {str(e)}"]
                }
            }

    def _build_mdl_from_workflow_tables(self, tables: List[Any], domain_context: DomainContext) -> str:
        """Build MDL representation from workflow tables for the relationship service"""
        try:
            mdl_structure = {
                "tables": [],
                "domain": {
                    "id": domain_context.domain_id,
                    "name": domain_context.domain_name,
                    "business_domain": domain_context.business_domain,
                    "purpose": domain_context.purpose
                }
            }
            
            for table in tables:
                table_name = table.name if hasattr(table, 'name') else table.get('name', 'unknown')
                table_description = table.description if hasattr(table, 'description') else f"Table for {table_name}"
                
                # Get columns from table metadata
                columns = table.metadata.get("columns", []) if hasattr(table, 'metadata') else []
                
                table_mdl = {
                    "name": table_name,
                    "description": table_description,
                    "columns": []
                }
                
                for col in columns:
                    column_mdl = {
                        "name": col.get("name", "unknown"),
                        "data_type": col.get("data_type", "VARCHAR"),
                        "description": col.get("description", ""),
                        "is_primary_key": col.get("is_primary_key", False),
                        "is_nullable": col.get("is_nullable", True),
                        "is_foreign_key": col.get("is_foreign_key", False)
                    }
                    table_mdl["columns"].append(column_mdl)
                
                mdl_structure["tables"].append(table_mdl)
            
            # Convert to JSON string for the relationship service
            import json
            return json.dumps(mdl_structure, indent=2)
            
        except Exception as e:
            logger.error(f"Error building MDL from workflow tables: {str(e)}")
            # Return minimal MDL structure
            return json.dumps({
                "tables": [{"name": "error", "description": "Error building MDL", "columns": []}],
                "domain": {"id": "error", "name": "Error", "business_domain": "Error", "purpose": "Error"}
            })

    def _process_relationship_recommendations(self, response: Dict[str, Any], tables: List[Any], domain_context: DomainContext) -> Dict[str, Any]:
        """Process the response from the existing relationship service"""
        try:
            # Extract relationships from the service response
            relationships = response.get("content", {}).get("relationships", [])
            
            # Convert to our workflow format
            processed_recommendations = {
                "domain_id": domain_context.domain_id,
                "total_tables": len(tables),
                "generated_at": datetime.now().isoformat(),
                "relationships": [],
                "summary": {
                    "total_relationships": len(relationships),
                    "high_priority_relationships": [],
                    "medium_priority_relationships": [],
                    "low_priority_relationships": [],
                    "recommendations": []
                }
            }
            
            # Process each relationship from the service
            for rel in relationships:
                processed_rel = {
                    "from_table": rel.get("source", ""),
                    "to_table": rel.get("target", ""),
                    "relationship_type": rel.get("type", "many_to_one").lower().replace(" ", "_"),
                    "description": rel.get("explanation", ""),
                    "confidence_score": 0.8,  # Default confidence for LLM-generated relationships
                    "source": "llm_generated",
                    "reasoning": rel.get("explanation", ""),
                    "suggested_action": "Review and validate against business requirements"
                }
                
                processed_recommendations["relationships"].append(processed_rel)
                
                # Categorize by confidence
                if processed_rel["confidence_score"] > 0.8:
                    processed_recommendations["summary"]["high_priority_relationships"].append(processed_rel)
                elif processed_rel["confidence_score"] > 0.6:
                    processed_recommendations["summary"]["medium_priority_relationships"].append(processed_rel)
                else:
                    processed_recommendations["summary"]["low_priority_relationships"].append(processed_rel)
            
            # Generate recommendations
            processed_recommendations["summary"]["recommendations"] = [
                f"Review {len(processed_recommendations['summary']['high_priority_relationships'])} high-confidence relationships",
                f"Validate {len(processed_recommendations['summary']['medium_priority_relationships'])} medium-confidence relationships",
                "Consider business context for all relationships",
                "Implement foreign key constraints for validated relationships"
            ]
            
            return processed_recommendations
            
        except Exception as e:
            logger.error(f"Error processing relationship recommendations: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to process relationship recommendations",
                "relationships": [],
                "summary": {
                    "total_relationships": 0,
                    "recommendations": [f"Error during processing: {str(e)}"]
                }
            }



    async def add_custom_relationship(self, relationship_data: Dict[str, Any], domain_context: DomainContext) -> Dict[str, Any]:
        """
        Add a custom relationship to the workflow state
        
        This allows users to manually define relationships that may not have been
        automatically detected by the LLM analysis.
        
        Args:
            relationship_data: Dictionary containing relationship information
            domain_context: The domain context for the relationship
        
        Returns:
            Dictionary containing the created relationship and status
        """
        try:
            state = self.get_workflow_state()
            
            # Validate relationship data
            required_fields = ["from_table", "to_table", "relationship_type"]
            for field in required_fields:
                if field not in relationship_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Create relationship object
            relationship = {
                "relationship_id": str(uuid4()),
                "domain_id": domain_context.domain_id,
                "name": relationship_data.get("name", f"{relationship_data['from_table']}_to_{relationship_data['to_table']}"),
                "relationship_type": relationship_data["relationship_type"],
                "from_table": relationship_data["from_table"],
                "to_table": relationship_data["to_table"],
                "from_column": relationship_data.get("from_column"),
                "to_column": relationship_data.get("to_column"),
                "description": relationship_data.get("description", f"Custom relationship between {relationship_data['from_table']} and {relationship_data['to_table']}"),
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "modified_by": self.user_id,
                "confidence_score": relationship_data.get("confidence_score", 1.0),
                "reasoning": relationship_data.get("reasoning", "Manually defined by user"),
                "source": "user_defined",
                "json_metadata": {
                    "workflow_session": self.session_id,
                    "user_notes": relationship_data.get("user_notes", ""),
                    "business_justification": relationship_data.get("business_justification", ""),
                    "implementation_notes": relationship_data.get("implementation_notes", "")
                }
            }
            
            # Add to workflow state
            state["relationships"].append(relationship)
            self.set_workflow_state(state)
            
            # Publish update
            publish_update(self.user_id, self.session_id or "default", {
                "type": "custom_relationship_added",
                "data": relationship
            })
            
            logger.info(f"Added custom relationship: {relationship['name']} between {relationship['from_table']} and {relationship['to_table']}")
            
            return {
                "status": "success",
                "relationship": relationship,
                "message": f"Successfully added relationship between {relationship['from_table']} and {relationship['to_table']}"
            }
            
        except Exception as e:
            logger.error(f"Error adding custom relationship: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to add custom relationship"
            }

    async def get_workflow_relationships(self) -> Dict[str, Any]:
        """Get all relationships currently defined in the workflow"""
        try:
            state = self.get_workflow_state()
            relationships = state.get("relationships", [])
            recommendations = state.get("relationship_recommendations", {})
            
            return {
                "status": "success",
                "relationships": relationships,
                "recommendations": recommendations,
                "summary": {
                    "total_relationships": len(relationships),
                    "total_recommendations": len(recommendations.get("table_recommendations", {})),
                    "workflow_progress": {
                        "tables_added": len(state.get("tables", [])),
                        "relationships_defined": len(relationships),
                        "recommendations_generated": bool(recommendations)
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting workflow relationships: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to get workflow relationships"
            }

    async def remove_relationship(self, relationship_id: str) -> Dict[str, Any]:
        """Remove a relationship from the workflow state"""
        try:
            state = self.get_workflow_state()
            relationships = state.get("relationships", [])
            
            # Find and remove the relationship
            original_count = len(relationships)
            state["relationships"] = [r for r in relationships if r.get("relationship_id") != relationship_id]
            
            if len(state["relationships"]) == original_count:
                return {
                    "status": "not_found",
                    "message": f"Relationship {relationship_id} not found in workflow"
                }
            
            self.set_workflow_state(state)
            
            # Publish update
            publish_update(self.user_id, self.session_id or "default", {
                "type": "relationship_removed",
                "data": {"relationship_id": relationship_id}
            })
            
            logger.info(f"Removed relationship {relationship_id} from workflow")
            
            return {
                "status": "success",
                "message": f"Successfully removed relationship {relationship_id}"
            }
            
        except Exception as e:
            logger.error(f"Error removing relationship: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to remove relationship"
            }

    async def update_relationship(self, relationship_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing relationship in the workflow state"""
        try:
            state = self.get_workflow_state()
            relationships = state.get("relationships", [])
            
            # Find and update the relationship
            for i, rel in enumerate(relationships):
                if rel.get("relationship_id") == relationship_id:
                    # Update fields
                    for key, value in updates.items():
                        if key in rel and key not in ["relationship_id", "created_at"]:
                            rel[key] = value
                    
                    # Update metadata
                    rel["modified_by"] = self.user_id
                    rel["updated_at"] = datetime.now().isoformat()
                    
                    # Update workflow state
                    self.set_workflow_state(state)
                    
                    # Publish update
                    publish_update(self.user_id, self.session_id or "default", {
                        "type": "relationship_updated",
                        "data": rel
                    })
                    
                    logger.info(f"Updated relationship {relationship_id}")
                    
                    return {
                        "status": "success",
                        "relationship": rel,
                        "message": f"Successfully updated relationship {relationship_id}"
                    }
            
            return {
                "status": "not_found",
                "message": f"Relationship {relationship_id} not found in workflow"
            }
            
        except Exception as e:
            logger.error(f"Error updating relationship: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to update relationship"
            }

    async def get_recommendations(self, add_table_request: AddTableRequest, domain_context: DomainContext, recommendation_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate comprehensive recommendations for a table including semantic descriptions and relationships
        
        Args:
            add_table_request: The table request containing schema information
            domain_context: The domain context for business domain understanding
            recommendation_types: List of recommendation types to generate. 
                                Defaults to ["semantic", "relationships", "optimization"]
        
        Returns:
            Dictionary containing all requested recommendations
        """
        if recommendation_types is None:
            recommendation_types = ["semantic", "relationships", "optimization"]
        
        recommendations = {
            "table_name": add_table_request.schema.table_name,
            "domain_id": domain_context.domain_id,
            "generated_at": datetime.now().isoformat(),
            "recommendation_types": recommendation_types,
            "results": {}
        }
        
        try:
            # Generate semantic description if requested
            if "semantic" in recommendation_types:
                logger.info(f"Generating semantic description for table {add_table_request.schema.table_name}")
                semantic_description = await self.get_semantic_description_for_table(add_table_request, domain_context)
                recommendations["results"]["semantic_description"] = semantic_description
            
            # Generate relationship recommendations if requested
            if "relationships" in recommendation_types:
                logger.info(f"Generating relationship recommendations for table {add_table_request.schema.table_name}")
                relationship_recommendations = await self.get_relationship_recommendation_for_table(add_table_request, domain_context)
                recommendations["results"]["relationship_recommendations"] = relationship_recommendations
            
            # Generate optimization recommendations if requested
            if "optimization" in recommendation_types:
                logger.info(f"Generating optimization recommendations for table {add_table_request.schema.table_name}")
                optimization_recommendations = await self._generate_optimization_recommendations(add_table_request, domain_context)
                recommendations["results"]["optimization_recommendations"] = optimization_recommendations
            
            # Generate data quality recommendations if requested
            if "data_quality" in recommendation_types:
                logger.info(f"Generating data quality recommendations for table {add_table_request.schema.table_name}")
                data_quality_recommendations = await self._generate_data_quality_recommendations(add_table_request, domain_context)
                recommendations["results"]["data_quality_recommendations"] = data_quality_recommendations
            
            # Generate summary and overall recommendations
            recommendations["summary"] = await self._generate_recommendations_summary(recommendations["results"])
            
            logger.info(f"Successfully generated {len(recommendation_types)} types of recommendations for table {add_table_request.schema.table_name}")
            
        except Exception as e:
            logger.error(f"Error generating recommendations for table {add_table_request.schema.table_name}: {str(e)}")
            recommendations["error"] = str(e)
            recommendations["status"] = "failed"
        
        return recommendations

    async def _generate_optimization_recommendations(self, add_table_request: AddTableRequest, domain_context: DomainContext) -> Dict[str, Any]:
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

    async def _generate_data_quality_recommendations(self, add_table_request: AddTableRequest, domain_context: DomainContext) -> Dict[str, Any]:
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

    async def add_table(self, add_table_request: AddTableRequest, domain_context: DomainContext):
        """Add table with enhanced column definitions and documentation"""
        state = self.get_workflow_state()
        schema_input = add_table_request.schema
        
        # Generate semantic description first
        semantic_description = await self.get_semantic_description_for_table(add_table_request, domain_context)
        
        # Generate relationship recommendations
        relationship_recommendations = await self.get_relationship_recommendation_for_table(add_table_request, domain_context)
        
        # LLM Table Definition (enhanced with semantic description)
        documented_table = await self.definition_manager.document_table_schema(schema_input, domain_context)
        
        # Add semantic description and relationship recommendations to the documented table
        documented_table.semantic_description = semantic_description
        documented_table.relationship_recommendations = relationship_recommendations
        
        # Create enhanced column definitions for metadata storage
        enhanced_columns_for_metadata = []
        for enhanced_col in documented_table.columns:
            enhanced_columns_for_metadata.append({
                "column_name": enhanced_col.column_name,
                "display_name": enhanced_col.display_name,
                "description": enhanced_col.description,
                "business_description": enhanced_col.business_description,
                "usage_type": enhanced_col.usage_type.value,
                "data_type": enhanced_col.data_type,
                "example_values": enhanced_col.example_values,
                "business_rules": enhanced_col.business_rules,
                "data_quality_checks": enhanced_col.data_quality_checks,
                "related_concepts": enhanced_col.related_concepts,
                "privacy_classification": enhanced_col.privacy_classification,
                "aggregation_suggestions": enhanced_col.aggregation_suggestions,
                "filtering_suggestions": enhanced_col.filtering_suggestions,
                "json_metadata": enhanced_col.json_metadata
            })
        
        # Create enhanced table object with all metadata including enhanced columns
        table = Table(
            name=schema_input.table_name,
            display_name=schema_input.table_name,
            description=documented_table.description,
            dataset_id=add_table_request.dataset_id,
            metadata={
                "columns": schema_input.columns,
                "enhanced_columns": enhanced_columns_for_metadata,
                "semantic_description": semantic_description.get("description", ""),
                "semantic_analysis": semantic_description,
                "relationship_recommendations": relationship_recommendations,
                "business_purpose": documented_table.business_purpose,
                "primary_use_cases": documented_table.primary_use_cases,
                "key_relationships": documented_table.key_relationships,
                "data_lineage": documented_table.data_lineage,
                "update_frequency": documented_table.update_frequency,
                "data_retention": documented_table.data_retention,
                "access_patterns": documented_table.access_patterns,
                "performance_considerations": documented_table.performance_considerations
            }
        )
        
        state["tables"].append(table)
        self.set_workflow_state(state)
        publish_update(self.user_id, self.session_id or "default", state)
        return documented_table

    async def create_enhanced_columns(self, documented_table, schema_input):
        """Create enhanced column definitions with LLM-generated insights"""
        enhanced_columns = []
        
        for i, col_data in enumerate(schema_input.columns):
            # Find corresponding enhanced column definition
            enhanced_col = None
            for enhanced_col_def in documented_table.columns:
                if enhanced_col_def.column_name == col_data.get("name"):
                    enhanced_col = enhanced_col_def
                    break
            
            # Prepare enhanced metadata
            enhanced_metadata = col_data.get("metadata", {})
            if enhanced_col:
                enhanced_metadata.update({
                    "business_description": enhanced_col.business_description,
                    "usage_type": enhanced_col.usage_type.value,
                    "example_values": enhanced_col.example_values,
                    "business_rules": enhanced_col.business_rules,
                    "data_quality_checks": enhanced_col.data_quality_checks,
                    "related_concepts": enhanced_col.related_concepts,
                    "privacy_classification": enhanced_col.privacy_classification,
                    "aggregation_suggestions": enhanced_col.aggregation_suggestions,
                    "filtering_suggestions": enhanced_col.filtering_suggestions,
                    "enhanced_metadata": enhanced_col.json_metadata
                })
            
            # Create enhanced column definition
            enhanced_column = {
                "table_id": None,  # Will be set when table is created
                "name": col_data.get("name", "unknown"),
                "display_name": enhanced_col.display_name if enhanced_col else (col_data.get("display_name") or col_data.get("name", "unknown")),
                "description": enhanced_col.description if enhanced_col else col_data.get("description"),
                "data_type": col_data.get("data_type"),
                "is_nullable": col_data.get("is_nullable", True),
                "is_primary_key": col_data.get("is_primary_key", False),
                "is_foreign_key": col_data.get("is_foreign_key", False),
                "usage_type": enhanced_col.usage_type.value if enhanced_col else col_data.get("usage_type"),
                "ordinal_position": i + 1,
                "json_metadata": enhanced_metadata,
                "enhanced_definition": {
                    "column_name": enhanced_col.column_name if enhanced_col else col_data.get("name"),
                    "display_name": enhanced_col.display_name if enhanced_col else (col_data.get("display_name") or col_data.get("name")),
                    "description": enhanced_col.description if enhanced_col else col_data.get("description"),
                    "business_description": enhanced_col.business_description if enhanced_col else "",
                    "usage_type": enhanced_col.usage_type.value if enhanced_col else col_data.get("usage_type"),
                    "data_type": enhanced_col.data_type if enhanced_col else col_data.get("data_type"),
                    "example_values": enhanced_col.example_values if enhanced_col else [],
                    "business_rules": enhanced_col.business_rules if enhanced_col else [],
                    "data_quality_checks": enhanced_col.data_quality_checks if enhanced_col else [],
                    "related_concepts": enhanced_col.related_concepts if enhanced_col else [],
                    "privacy_classification": enhanced_col.privacy_classification if enhanced_col else "internal",
                    "aggregation_suggestions": enhanced_col.aggregation_suggestions if enhanced_col else [],
                    "filtering_suggestions": enhanced_col.filtering_suggestions if enhanced_col else [],
                    "json_metadata": enhanced_col.json_metadata if enhanced_col else {}
                }
            }
            
            enhanced_columns.append(enhanced_column)
        
        return enhanced_columns

    async def get_enhanced_table_response(self, table, documented_table, enhanced_columns, column_count):
        """Create enhanced table response with all column definitions"""
        # Convert EnhancedColumnDefinition objects to dictionaries for response
        response_enhanced_columns = []
        for enhanced_col in documented_table.columns:
            response_enhanced_columns.append({
                "column_name": enhanced_col.column_name,
                "display_name": enhanced_col.display_name,
                "description": enhanced_col.description,
                "business_description": enhanced_col.business_description,
                "usage_type": enhanced_col.usage_type.value,
                "data_type": enhanced_col.data_type,
                "example_values": enhanced_col.example_values,
                "business_rules": enhanced_col.business_rules,
                "data_quality_checks": enhanced_col.data_quality_checks,
                "related_concepts": enhanced_col.related_concepts,
                "privacy_classification": enhanced_col.privacy_classification,
                "aggregation_suggestions": enhanced_col.aggregation_suggestions,
                "filtering_suggestions": enhanced_col.filtering_suggestions,
                "json_metadata": enhanced_col.json_metadata
            })
        
        return {
            "table_id": table.table_id,
            "name": table.name,
            "display_name": table.display_name,
            "description": table.description,
            "table_type": table.table_type,
            "semantic_description": documented_table.description,
            "column_count": column_count,
            "business_purpose": documented_table.business_purpose,
            "primary_use_cases": documented_table.primary_use_cases,
            "key_relationships": documented_table.key_relationships,
            "data_lineage": documented_table.data_lineage,
            "update_frequency": documented_table.update_frequency,
            "data_retention": documented_table.data_retention,
            "access_patterns": documented_table.access_patterns,
            "performance_considerations": documented_table.performance_considerations,
            "enhanced_columns": response_enhanced_columns
        }

    async def get_enhanced_columns_for_table(self, table_id: str, db_session: AsyncSession):
        """Get enhanced column definitions for an existing table"""
        try:
            # Get table with columns
            table = await db_session.execute(
                select(Table)
                .options(selectinload(Table.columns))
                .where(Table.table_id == table_id)
            )
            table = table.scalar_one_or_none()
            
            if not table:
                raise ValueError(f"Table {table_id} not found")
            
            # Check if enhanced columns are already stored in table metadata
            table_metadata = table.json_metadata or {}
            stored_enhanced_columns = table_metadata.get("enhanced_columns", [])
            
            if stored_enhanced_columns:
                # Return stored enhanced columns
                logger.info(f"Found {len(stored_enhanced_columns)} stored enhanced columns for table {table_id}")
                return {
                    "table_id": table.table_id,
                    "table_name": table.name,
                    "enhanced_columns": stored_enhanced_columns,
                    "source": "stored_metadata"
                }
            
            # If no stored enhanced columns, generate them using LLM
            logger.info(f"No stored enhanced columns found for table {table_id}, generating with LLM")
            
            # Get domain context
            domain = await db_session.execute(
                select(Domain).where(Domain.domain_id == table.domain_id)
            )
            domain = domain.scalar_one_or_none()
            
            if not domain:
                raise ValueError("Domain not found")
            
            # Create domain context for LLM processing
            domain_context = DomainContext(
                domain_id=domain.domain_id,
                domain_name=domain.display_name,
                business_domain="",  # Would need to be stored in domain
                purpose=domain.description or "",
                target_users=[],  # Would need to be stored in domain
                key_business_concepts=[],  # Would need to be stored in domain
                data_sources=None,
                compliance_requirements=None
            )
            
            # Convert existing columns to schema input format
            columns = []
            for col in table.columns:
                columns.append({
                    "name": col.name,
                    "data_type": col.data_type,
                    "nullable": col.is_nullable,
                    "primary_key": col.is_primary_key,
                    "description": col.description,
                    "usage_type": col.usage_type,
                    "metadata": col.json_metadata or {}
                })
            
            schema_input = SchemaInput(
                table_name=table.name,
                table_description=table.description,
                columns=columns,
                sample_data=None,
                constraints=None
            )
            
            # Generate enhanced column definitions
            documented_table = await self.definition_manager.document_table_schema(schema_input, domain_context)
            
            # Convert to response format
            enhanced_columns = []
            for enhanced_col in documented_table.columns:
                enhanced_columns.append({
                    "column_name": enhanced_col.column_name,
                    "display_name": enhanced_col.display_name,
                    "description": enhanced_col.description,
                    "business_description": enhanced_col.business_description,
                    "usage_type": enhanced_col.usage_type.value,
                    "data_type": enhanced_col.data_type,
                    "example_values": enhanced_col.example_values,
                    "business_rules": enhanced_col.business_rules,
                    "data_quality_checks": enhanced_col.data_quality_checks,
                    "related_concepts": enhanced_col.related_concepts,
                    "privacy_classification": enhanced_col.privacy_classification,
                    "aggregation_suggestions": enhanced_col.aggregation_suggestions,
                    "filtering_suggestions": enhanced_col.filtering_suggestions,
                    "json_metadata": enhanced_col.json_metadata
                })
            
            # Store the generated enhanced columns in table metadata for future use
            if enhanced_columns:
                table_metadata["enhanced_columns"] = enhanced_columns
                table.json_metadata = table_metadata
                await db_session.commit()
                logger.info(f"Stored {len(enhanced_columns)} generated enhanced columns in table metadata")
            
            return {
                "table_id": table.table_id,
                "table_name": table.name,
                "enhanced_columns": enhanced_columns,
                "source": "generated_and_stored"
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced columns: {str(e)}")
            raise

    async def commit_workflow(self, db_session):
        """Commit the workflow state to database and clean up cache"""
        state = self.get_workflow_state()
        domain_data = state.get("domain")
        if not domain_data:
            raise ValueError("No domain defined in workflow state.")
        
        # Include relationship information in the final commit
        relationships = state.get("relationships", [])
        relationship_recommendations = state.get("relationship_recommendations", {})
        
        # The actual database operations are now handled in the router
        # This method just cleans up the workflow state
        self.cache.delete(self._workflow_cache_key())
        publish_update(self.user_id, self.session_id or "default", {
            "status": "committed", 
            "domain": domain_data.get("domain_id"),
            "tables_count": len(state.get("tables", [])),
            "relationships_count": len(relationships),
            "recommendations_generated": bool(relationship_recommendations),
            "message": "Workflow committed successfully with relationships defined"
        })
        return state
    

class MetricsService:
    """Service for managing metrics, views, and calculated columns using LLMDefinitionGenerator"""
    
    def __init__(self, db: AsyncSession, domain_id: str = None):
        self.db = db
        self.domain_id = domain_id
        # Initialize LLM Definition Generator
        from app.agents.project_manager import LLMDefinitionGenerator
        self.llm_generator = LLMDefinitionGenerator()
    
    async def _get_domain_context(self, table_id: str) -> Dict[str, Any]:
        """Get domain context for LLM definition generation"""
        try:
            # Get table and its domain
            from sqlalchemy import select
            table = await self.db.execute(
                select(Table).where(Table.table_id == table_id)
            )
            table = table.scalar_one_or_none()
            
            if not table:
                raise ValueError(f"Table {table_id} not found")
            
            domain_id = table.domain_id
            
            # Get all tables in the domain
            tables = await self.db.execute(
                select(Table).where(Table.domain_id == domain_id)
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
            
            # Get domain metadata for business context
            domain = await self.db.execute(
                select(Domain).where(Domain.domain_id == domain_id)
            )
            domain = domain.scalar_one_or_none()
            
            business_context = {}
            if domain and domain.json_metadata:
                business_context = domain.json_metadata.get("business_context", {})
            
            return {
                "tables": table_context,
                "existing_metrics": existing_metrics,
                "business_context": business_context,
                "data_lineage": {}  # Could be enhanced with actual lineage data
            }
            
        except Exception as e:
            logger.error(f"Error getting domain context: {str(e)}")
            return {
                "tables": {},
                "existing_metrics": {},
                "business_context": {},
                "data_lineage": {}
            }
    
    async def add_metric(self, table_id: str, metric_data: MetricCreate, created_by: str) -> Metric:
        """Add metric to table using LLMDefinitionGenerator for enhancement"""
        try:
            # Get domain context
            context = await self._get_domain_context(table_id)
            
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
            # Get domain context
            context = await self._get_domain_context(table_id)
            
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
            # Get domain context
            context = await self._get_domain_context(table_id)
            
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

    async def enhance_metric_definition(self, metric_id: str, user_id: str) -> dict:
        """Enhance an existing metric definition using LLM without saving to database"""
        try:
            # Get the metric
            from sqlalchemy import select
            metric = await self.db.execute(
                select(Metric).where(Metric.metric_id == metric_id)
            )
            metric = metric.scalar_one_or_none()
            
            if not metric:
                raise ValueError(f"Metric {metric_id} not found")
            
            # Create UserExample from existing metric data
            from app.service.models import UserExample, DefinitionType
            user_example = UserExample(
                definition_type=DefinitionType.METRIC,
                name=metric.name,
                description=metric.description or f"Metric for {metric.name}",
                sql=metric.metric_sql,
                additional_context={
                    "metric_type": metric.metric_type,
                    "aggregation_type": metric.aggregation_type,
                    "business_purpose": metric.description,
                    "existing_metadata": metric.json_metadata or {}
                },
                user_id=user_id
            )
            
            # Get domain context for enhancement
            context = await self._get_domain_context(metric.table_id)
            
            # Generate enhanced definition using LLM
            enhanced_definition = await self.llm_generator.generate_metric_definition(user_example, context)
            
            # Return the enhanced definition without saving to database
            return {
                "metric_id": metric_id,
                "original_metric": {
                    "name": metric.name,
                    "display_name": metric.display_name,
                    "description": metric.description,
                    "metric_sql": metric.metric_sql,
                    "metric_type": metric.metric_type,
                    "aggregation_type": metric.aggregation_type,
                    "format_string": metric.format_string
                },
                "enhanced_definition": {
                    "name": enhanced_definition.name,
                    "display_name": enhanced_definition.display_name,
                    "description": enhanced_definition.description,
                    "sql_query": enhanced_definition.sql_query,
                    "metadata": enhanced_definition.metadata,
                    "chain_of_thought": enhanced_definition.chain_of_thought,
                    "confidence_score": enhanced_definition.confidence_score,
                    "suggestions": enhanced_definition.suggestions,
                    "related_tables": enhanced_definition.related_tables,
                    "related_columns": enhanced_definition.related_columns
                },
                "enhancement_summary": {
                    "improvements_made": len(enhanced_definition.suggestions) if enhanced_definition.suggestions else 0,
                    "confidence_level": enhanced_definition.confidence_score,
                    "recommended_changes": enhanced_definition.suggestions or []
                }
            }
            
        except Exception as e:
            logger.error(f"Error enhancing metric definition: {str(e)}")
            raise

    async def apply_metric_enhancement(self, metric_id: str, enhancement_data: dict, user_id: str, session_id: str) -> Metric:
        """Apply LLM enhancement to an existing metric"""
        try:
            # Get the metric
            from sqlalchemy import select, func
            metric = await self.db.execute(
                select(Metric).where(Metric.metric_id == metric_id)
            )
            metric = metric.scalar_one_or_none()
            
            if not metric:
                raise ValueError(f"Metric {metric_id} not found")
            
            # Extract enhancement data
            enhanced_definition = enhancement_data.get("enhanced_definition", {})
            
            # Update metric with enhanced data
            if enhanced_definition.get("name"):
                metric.name = enhanced_definition["name"]
            if enhanced_definition.get("display_name"):
                metric.display_name = enhanced_definition["display_name"]
            if enhanced_definition.get("description"):
                metric.description = enhanced_definition["description"]
            if enhanced_definition.get("sql_query"):
                metric.metric_sql = enhanced_definition["sql_query"]
            if enhanced_definition.get("metadata", {}).get("metric_type"):
                metric.metric_type = enhanced_definition["metadata"]["metric_type"]
            if enhanced_definition.get("metadata", {}).get("aggregation_type"):
                metric.aggregation_type = enhanced_definition["metadata"]["aggregation_type"]
            if enhanced_definition.get("metadata", {}).get("format_string"):
                metric.format_string = enhanced_definition["metadata"]["format_string"]
            
            # Update metadata with enhancement information
            current_metadata = metric.json_metadata or {}
            current_metadata.update({
                "enhanced_at": func.now(),
                "enhanced_by": user_id,
                "enhancement_session": session_id,
                "chain_of_thought": enhanced_definition.get("chain_of_thought"),
                "confidence_score": enhanced_definition.get("confidence_score"),
                "suggestions": enhanced_definition.get("suggestions"),
                "related_tables": enhanced_definition.get("related_tables"),
                "related_columns": enhanced_definition.get("related_columns"),
                "enhancement_metadata": enhanced_definition.get("metadata", {}),
                "original_metric": {
                    "name": metric.name,
                    "description": metric.description,
                    "metric_sql": metric.metric_sql,
                    "metric_type": metric.metric_type,
                    "aggregation_type": metric.aggregation_type
                }
            })
            metric.json_metadata = current_metadata
            
            # Update version and modified info
            metric.modified_by = user_id
            metric.entity_version += 1
            
            await self.db.commit()
            await self.db.refresh(metric)
            
            logger.info(f"Applied enhancement to metric '{metric.name}' with confidence score {enhanced_definition.get('confidence_score', 0)}")
            return metric
            
        except Exception as e:
            logger.error(f"Error applying metric enhancement: {str(e)}")
            raise

    async def enhance_view_definition(self, view_id: str, user_id: str) -> dict:
        """Enhance an existing view definition using LLM without saving to database"""
        try:
            # Get the view
            from sqlalchemy import select
            view = await self.db.execute(
                select(View).where(View.view_id == view_id)
            )
            view = view.scalar_one_or_none()
            
            if not view:
                raise ValueError(f"View {view_id} not found")
            
            # Create UserExample from existing view data
            from app.service.models import UserExample, DefinitionType
            user_example = UserExample(
                definition_type=DefinitionType.VIEW,
                name=view.name,
                description=view.description or f"View for {view.name}",
                sql=view.view_sql,
                additional_context={
                    "view_type": view.view_type,
                    "business_purpose": view.description,
                    "target_audience": "business_analysts",
                    "existing_metadata": view.json_metadata or {}
                },
                user_id=user_id
            )
            
            # Get domain context for enhancement
            context = await self._get_domain_context(view.table_id)
            
            # Generate enhanced definition using LLM
            enhanced_definition = await self.llm_generator.generate_view_definition(user_example, context)
            
            # Return the enhanced definition without saving to database
            return {
                "view_id": view_id,
                "original_view": {
                    "name": view.name,
                    "display_name": view.display_name,
                    "description": view.description,
                    "view_sql": view.view_sql,
                    "view_type": view.view_type
                },
                "enhanced_definition": {
                    "name": enhanced_definition.name,
                    "display_name": enhanced_definition.display_name,
                    "description": enhanced_definition.description,
                    "sql_query": enhanced_definition.sql_query,
                    "metadata": enhanced_definition.metadata,
                    "chain_of_thought": enhanced_definition.chain_of_thought,
                    "confidence_score": enhanced_definition.confidence_score,
                    "suggestions": enhanced_definition.suggestions,
                    "related_tables": enhanced_definition.related_tables,
                    "related_columns": enhanced_definition.related_columns
                },
                "enhancement_summary": {
                    "improvements_made": len(enhanced_definition.suggestions) if enhanced_definition.suggestions else 0,
                    "confidence_level": enhanced_definition.confidence_score,
                    "recommended_changes": enhanced_definition.suggestions or []
                }
            }
            
        except Exception as e:
            logger.error(f"Error enhancing view definition: {str(e)}")
            raise

    async def apply_view_enhancement(self, view_id: str, enhancement_data: dict, user_id: str, session_id: str) -> View:
        """Apply LLM enhancement to an existing view"""
        try:
            # Get the view
            from sqlalchemy import select, func
            view = await self.db.execute(
                select(View).where(View.view_id == view_id)
            )
            view = view.scalar_one_or_none()
            
            if not view:
                raise ValueError(f"View {view_id} not found")
            
            # Extract enhancement data
            enhanced_definition = enhancement_data.get("enhanced_definition", {})
            
            # Update view with enhanced data
            if enhanced_definition.get("name"):
                view.name = enhanced_definition["name"]
            if enhanced_definition.get("display_name"):
                view.display_name = enhanced_definition["display_name"]
            if enhanced_definition.get("description"):
                view.description = enhanced_definition["description"]
            if enhanced_definition.get("sql_query"):
                view.view_sql = enhanced_definition["sql_query"]
            if enhanced_definition.get("metadata", {}).get("view_type"):
                view.view_type = enhanced_definition["metadata"]["view_type"]
            
            # Update metadata with enhancement information
            current_metadata = view.json_metadata or {}
            current_metadata.update({
                "enhanced_at": func.now(),
                "enhanced_by": user_id,
                "enhancement_session": session_id,
                "chain_of_thought": enhanced_definition.get("chain_of_thought"),
                "confidence_score": enhanced_definition.get("confidence_score"),
                "suggestions": enhanced_definition.get("suggestions"),
                "related_tables": enhanced_definition.get("related_tables"),
                "related_columns": enhanced_definition.get("related_columns"),
                "enhancement_metadata": enhanced_definition.get("metadata", {}),
                "original_view": {
                    "name": view.name,
                    "description": view.description,
                    "view_sql": view.view_sql,
                    "view_type": view.view_type
                }
            })
            view.json_metadata = current_metadata
            
            # Update version and modified info
            view.modified_by = user_id
            view.entity_version += 1
            
            await self.db.commit()
            await self.db.refresh(view)
            
            logger.info(f"Applied enhancement to view '{view.name}' with confidence score {enhanced_definition.get('confidence_score', 0)}")
            return view
            
        except Exception as e:
            logger.error(f"Error applying view enhancement: {str(e)}")
            raise

    async def enhance_calculated_column_definition(self, column_id: str, user_id: str) -> dict:
        """Enhance an existing calculated column definition using LLM without saving to database"""
        try:
            # Get the calculated column
            from sqlalchemy import select
            column = await self.db.execute(
                select(SQLColumn)
                .options(selectinload(SQLColumn.calculated_column))
                .where(SQLColumn.column_id == column_id)
            )
            column = column.scalar_one_or_none()
            
            if not column:
                raise ValueError(f"Column {column_id} not found")
            
            if column.column_type != 'calculated_column':
                raise ValueError(f"Column {column_id} is not a calculated column")
            
            # Create UserExample from existing calculated column data
            from app.service.models import UserExample, DefinitionType
            user_example = UserExample(
                definition_type=DefinitionType.CALCULATED_COLUMN,
                name=column.name,
                description=column.description or f"Calculated column {column.name}",
                sql=column.calculated_column.calculation_sql,
                additional_context={
                    "data_type": column.data_type,
                    "usage_type": column.usage_type,
                    "dependencies": column.calculated_column.dependencies or [],
                    "business_purpose": column.description,
                    "existing_metadata": column.json_metadata or {}
                },
                user_id=user_id
            )
            
            # Get domain context for enhancement
            context = await self._get_domain_context(column.table_id)
            
            # Generate enhanced definition using LLM
            enhanced_definition = await self.llm_generator.generate_calculated_column_definition(user_example, context)
            
            # Return the enhanced definition without saving to database
            return {
                "column_id": column_id,
                "original_calculated_column": {
                    "name": column.name,
                    "display_name": column.display_name,
                    "description": column.description,
                    "data_type": column.data_type,
                    "usage_type": column.usage_type,
                    "calculation_sql": column.calculated_column.calculation_sql,
                    "dependencies": column.calculated_column.dependencies,
                    "function_id": column.calculated_column.function_id
                },
                "enhanced_definition": {
                    "name": enhanced_definition.name,
                    "display_name": enhanced_definition.display_name,
                    "description": enhanced_definition.description,
                    "sql_query": enhanced_definition.sql_query,
                    "metadata": enhanced_definition.metadata,
                    "chain_of_thought": enhanced_definition.chain_of_thought,
                    "confidence_score": enhanced_definition.confidence_score,
                    "suggestions": enhanced_definition.suggestions,
                    "related_tables": enhanced_definition.related_tables,
                    "related_columns": enhanced_definition.related_columns
                },
                "enhancement_summary": {
                    "improvements_made": len(enhanced_definition.suggestions) if enhanced_definition.suggestions else 0,
                    "confidence_level": enhanced_definition.confidence_score,
                    "recommended_changes": enhanced_definition.suggestions or []
                }
            }
            
        except Exception as e:
            logger.error(f"Error enhancing calculated column definition: {str(e)}")
            raise

    async def apply_calculated_column_enhancement(self, column_id: str, enhancement_data: dict, user_id: str, session_id: str) -> SQLColumn:
        """Apply LLM enhancement to an existing calculated column"""
        try:
            # Get the calculated column
            from sqlalchemy import select, func
            column = await self.db.execute(
                select(SQLColumn)
                .options(selectinload(SQLColumn.calculated_column))
                .where(SQLColumn.column_id == column_id)
            )
            column = column.scalar_one_or_none()
            
            if not column:
                raise ValueError(f"Column {column_id} not found")
            
            if column.column_type != 'calculated_column':
                raise ValueError(f"Column {column_id} is not a calculated column")
            
            # Extract enhancement data
            enhanced_definition = enhancement_data.get("enhanced_definition", {})
            
            # Update column with enhanced data
            if enhanced_definition.get("name"):
                column.name = enhanced_definition["name"]
            if enhanced_definition.get("display_name"):
                column.display_name = enhanced_definition["display_name"]
            if enhanced_definition.get("description"):
                column.description = enhanced_definition["description"]
            if enhanced_definition.get("metadata", {}).get("data_type"):
                column.data_type = enhanced_definition["metadata"]["data_type"]
            if enhanced_definition.get("metadata", {}).get("usage_type"):
                column.usage_type = enhanced_definition["metadata"]["usage_type"]
            
            # Update calculated column with enhanced data
            if enhanced_definition.get("sql_query"):
                column.calculated_column.calculation_sql = enhanced_definition["sql_query"]
            if enhanced_definition.get("metadata", {}).get("dependencies"):
                column.calculated_column.dependencies = enhanced_definition["metadata"]["dependencies"]
            
            # Update metadata with enhancement information
            current_metadata = column.json_metadata or {}
            current_metadata.update({
                "enhanced_at": func.now(),
                "enhanced_by": user_id,
                "enhancement_session": session_id,
                "chain_of_thought": enhanced_definition.get("chain_of_thought"),
                "confidence_score": enhanced_definition.get("confidence_score"),
                "suggestions": enhanced_definition.get("suggestions"),
                "related_tables": enhanced_definition.get("related_tables"),
                "related_columns": enhanced_definition.get("related_columns"),
                "enhancement_metadata": enhanced_definition.get("metadata", {}),
                "original_calculated_column": {
                    "name": column.name,
                    "description": column.description,
                    "data_type": column.data_type,
                    "usage_type": column.usage_type,
                    "calculation_sql": column.calculated_column.calculation_sql,
                    "dependencies": column.calculated_column.dependencies
                }
            })
            column.json_metadata = current_metadata
            
            # Update version and modified info
            column.modified_by = user_id
            column.entity_version += 1
            column.calculated_column.modified_by = user_id
            column.calculated_column.entity_version += 1
            
            await self.db.commit()
            await self.db.refresh(column)
            
            logger.info(f"Applied enhancement to calculated column '{column.name}' with confidence score {enhanced_definition.get('confidence_score', 0)}")
            return column
            
        except Exception as e:
            logger.error(f"Error applying calculated column enhancement: {str(e)}")
            raise