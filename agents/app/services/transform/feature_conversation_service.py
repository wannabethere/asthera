"""
Feature Conversation Streaming Service

This service provides a streaming conversation interface for feature recommendation.
It allows users to:
1. Continuously ask for feature recommendations
2. Select features from recommendations
3. Save selected features to a file
4. Maintain conversation context across multiple turns

The service streams updates as features are being generated, allowing for real-time
feedback in the chat UX.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import uuid4

from app.services.servicebase import BaseService
from app.agents.pipelines.transform import (
    TransformationPipeline,
    FeatureRecommendationRequest,
    FeatureRecommendationResponse,
    ConversationContext,
    FeatureRegistryEntry
)
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm
from app.utils.streaming import streaming_manager

logger = logging.getLogger("lexy-ai-service")


class FeatureConversationRequest(BaseModel):
    """Request model for feature conversation"""
    query_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique conversation ID")
    user_query: str = Field(..., description="User's question or request for features")
    project_id: str = Field(..., description="Project identifier")
    domain: str = Field(default="cybersecurity", description="Domain context")
    action: str = Field(default="recommend", description="Action: 'recommend', 'select', 'save', or 'finalize'")
    selected_feature_ids: Optional[List[str]] = Field(default=None, description="Feature IDs to select (for 'select' action)")
    save_path: Optional[str] = Field(default=None, description="Path to save features (for 'save' action)")
    auto_save: bool = Field(default=False, description="Automatically save selected features to file (for 'select' action)")
    # Finalization fields
    workflow_name: Optional[str] = Field(default=None, description="Name for the finalized workflow (for 'finalize' action)")
    workflow_description: Optional[str] = Field(default=None, description="Description for the finalized workflow (for 'finalize' action)")
    workflow_type: Optional[str] = Field(default="feature_registry", description="Type of workflow (for 'finalize' action)")
    version: Optional[str] = Field(default=None, description="Version string (e.g., '1.0.0'). Auto-generated if not provided (for 'finalize' action)")


class FeatureConversationResponse(BaseModel):
    """Response model for feature conversation"""
    query_id: str
    status: str = Field(..., description="Status: 'processing', 'recommending', 'finished', 'error'")
    recommended_features: List[Dict[str, Any]] = Field(default_factory=list)
    selected_features: List[Dict[str, Any]] = Field(default_factory=list)
    total_selected: int = Field(default=0)
    conversation_context: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None


class FeatureConversationService(BaseService[FeatureConversationRequest, FeatureConversationResponse]):
    """
    Service for streaming feature conversation with persistent state management.
    
    This service wraps the TransformationPipeline and provides:
    - Streaming updates during feature generation
    - Conversation context management
    - Feature selection tracking
    - File persistence for selected features
    """
    
    def __init__(
        self,
        pipeline: Optional[TransformationPipeline] = None,
        save_directory: Optional[str] = None,
        maxsize: int = 1_000_000,
        ttl: int = 3600,  # 1 hour for conversation context
    ):
        """Initialize the feature conversation service
        
        Args:
            pipeline: Optional TransformationPipeline instance (will create if not provided)
            save_directory: Directory to save selected features (defaults to ./feature_registry)
            maxsize: Maximum cache size
            ttl: Time to live for cached conversations
        """
        # Initialize with empty pipelines dict (we use our own pipeline)
        super().__init__(pipelines={}, maxsize=maxsize, ttl=ttl)
        
        # Initialize transformation pipeline
        self._pipeline = pipeline or TransformationPipeline(
            llm=get_llm(temperature=0, model="gpt-4o-mini"),
            retrieval_helper=RetrievalHelper()
        )
        
        # Pipeline will be initialized on first use
        self._pipeline_initialized = False
        
        # Set up save directory
        if save_directory:
            self._save_directory = Path(save_directory)
        else:
            # Default to feature_registry in the project root
            self._save_directory = Path(__file__).parent.parent.parent.parent / "feature_registry"
        
        self._save_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Feature conversation service initialized. Save directory: {self._save_directory}")
    
    async def _ensure_pipeline_initialized(self):
        """Ensure pipeline is initialized"""
        if not self._pipeline_initialized:
            await self._pipeline.initialize()
            self._pipeline_initialized = True
    
    async def _process_request_impl(self, request: FeatureConversationRequest) -> Any:
        """Process a feature conversation request
        
        Args:
            request: Feature conversation request
            
        Returns:
            Processing result
        """
        # Ensure pipeline is initialized
        await self._ensure_pipeline_initialized()
        
        # Route to appropriate handler based on action
        if request.action == "recommend":
            return await self._handle_recommend(request)
        elif request.action == "select":
            return await self._handle_select(request)
        elif request.action == "save":
            return await self._handle_save(request)
        elif request.action == "finalize":
            return await self._handle_finalize(request)
        else:
            raise ValueError(f"Unknown action: {request.action}")
    
    async def _handle_recommend(self, request: FeatureConversationRequest) -> Dict[str, Any]:
        """Handle feature recommendation request"""
        try:
            # Get or create conversation context
            context = self._pipeline.get_conversation_context(
                request.project_id,
                request.domain
            )
            
            # Create recommendation request
            recommendation_request = FeatureRecommendationRequest(
                user_query=request.user_query,
                project_id=request.project_id,
                domain=request.domain,
                conversation_context=context,
                include_risk_features=True,
                include_impact_features=True,
                include_likelihood_features=True
            )
            
            # Get recommendations
            response = await self._pipeline.recommend_features(recommendation_request)
            
            if not response.success:
                return {
                    "status": "error",
                    "error": response.error,
                    "recommended_features": []
                }
            
            # Convert features to dict format
            features = [self._feature_to_dict(f) for f in response.recommended_features]
            
            # Include cache metadata
            metadata = response.metadata or {}
            new_count = metadata.get("new_features_count", len(features))
            existing_count = metadata.get("existing_features_count", 0)
            total_in_registry = metadata.get("total_in_registry", len(features))
            selected_used = metadata.get("selected_features_used", 0)
            selected_names = metadata.get("selected_feature_names", [])
            
            message = f"Generated {len(features)} feature recommendations"
            if new_count > 0 and existing_count > 0:
                message += f" ({new_count} new, {existing_count} from cache)"
            elif existing_count > 0:
                message += f" (all from cache)"
            if selected_used > 0:
                message += f" - Built upon {selected_used} previously selected features"
            
            return {
                "status": "finished",
                "recommended_features": features,
                "conversation_context": self._context_to_dict(response.conversation_context),
                "message": message,
                "metadata": {
                    "new_features_count": new_count,
                    "existing_features_count": existing_count,
                    "total_in_registry": total_in_registry,
                    "selected_features_used": selected_used,
                    "selected_feature_names": selected_names
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling recommend request: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "recommended_features": []
            }
    
    async def _handle_select(self, request: FeatureConversationRequest) -> Dict[str, Any]:
        """Handle feature selection request - stores selected features in cache and optionally saves to file"""
        try:
            if not request.selected_feature_ids:
                return {
                    "status": "error",
                    "error": "No feature IDs provided for selection"
                }
            
            # Get conversation context
            context = self._pipeline.get_conversation_context(
                request.project_id,
                request.domain
            )
            
            if not context:
                return {
                    "status": "error",
                    "error": "No active conversation found. Please recommend features first."
                }
            
            # Select features (this updates the cache with selected status)
            result = await self._pipeline.select_features(
                feature_ids=request.selected_feature_ids,
                conversation_context=context
            )
            
            if not result["success"]:
                return {
                    "status": "error",
                    "error": "Failed to select features"
                }
            
            # Get selected features from cache
            selected_features = [
                self._feature_to_dict(context.feature_registry[fid])
                for fid in request.selected_feature_ids
                if fid in context.feature_registry
            ]
            
            # Features are now stored in cache with SELECTED status
            logger.info(f"Selected {len(selected_features)} features - stored in cache. Total selected: {len(context.selected_features)}")
            
            response_data = {
                "status": "finished",
                "selected_features": selected_features,
                "total_selected": len(context.selected_features),
                "conversation_context": self._context_to_dict(context),
                "message": f"Selected {len(selected_features)} features and stored in cache"
            }
            
            # Auto-save to file if requested
            if request.auto_save:
                save_result = await self._save_selected_features_to_file(
                    context=context,
                    project_id=request.project_id,
                    domain=request.domain,
                    save_path=request.save_path
                )
                if save_result.get("status") == "finished":
                    response_data["message"] += f" and saved to {save_result.get('save_path')}"
                    response_data["save_path"] = save_result.get("save_path")
                else:
                    response_data["save_warning"] = save_result.get("error", "Failed to auto-save")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error handling select request: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _save_selected_features_to_file(
        self,
        context: ConversationContext,
        project_id: str,
        domain: str,
        save_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Internal method to save selected features to file"""
        try:
            if not context.selected_features:
                return {
                    "status": "error",
                    "error": "No features selected to save"
                }
            
            # Get selected features from registry
            selected_entries = [
                context.feature_registry[fid]
                for fid in context.selected_features
                if fid in context.feature_registry
            ]
            
            # Determine save path
            if save_path:
                save_path_obj = Path(save_path)
            else:
                # Generate default filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"selected_features_{project_id}_{domain}_{timestamp}.json"
                save_path_obj = self._save_directory / filename
            
            # Ensure directory exists
            save_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data for saving
            save_data = {
                "project_id": project_id,
                "domain": domain,
                "saved_at": datetime.now().isoformat(),
                "total_features": len(selected_entries),
                "features": [self._feature_to_dict(entry) for entry in selected_entries],
                "conversation_summary": {
                    "total_queries": len(context.previous_queries),
                    "compliance_framework": context.compliance_framework,
                    "severity_levels": context.severity_levels,
                    "sla_requirements": context.sla_requirements
                }
            }
            
            # Save to file
            with open(save_path_obj, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, default=str)
            
            logger.info(f"Saved {len(selected_entries)} selected features to {save_path_obj}")
            
            return {
                "status": "finished",
                "total_selected": len(selected_entries),
                "save_path": str(save_path_obj),
                "message": f"Saved {len(selected_entries)} features to {save_path_obj}"
            }
            
        except Exception as e:
            logger.error(f"Error saving selected features: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _handle_save(self, request: FeatureConversationRequest) -> Dict[str, Any]:
        """Handle save request - save selected features from cache to file"""
        try:
            # Get conversation context
            context = self._pipeline.get_conversation_context(
                request.project_id,
                request.domain
            )
            
            if not context:
                return {
                    "status": "error",
                    "error": "No active conversation found"
                }
            
            # Use the internal save method
            return await self._save_selected_features_to_file(
                context=context,
                project_id=request.project_id,
                domain=request.domain,
                save_path=request.save_path
            )
            
        except Exception as e:
            logger.error(f"Error handling save request: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _handle_finalize(self, request: FeatureConversationRequest) -> Dict[str, Any]:
        """Handle finalize request - create a finalized, versioned feature workflow"""
        try:
            # Get conversation context
            context = self._pipeline.get_conversation_context(
                request.project_id,
                request.domain
            )
            
            if not context:
                return {
                    "status": "error",
                    "error": "No active conversation found"
                }
            
            if not context.selected_features:
                return {
                    "status": "error",
                    "error": "No features selected to finalize. Please select features first."
                }
            
            # Get selected features from registry
            selected_entries = [
                context.feature_registry[fid]
                for fid in context.selected_features
                if fid in context.feature_registry
            ]
            
            # Generate version if not provided
            version = request.version
            if not version:
                # Check for existing finalized workflows to determine next version
                version = self._get_next_version(
                    project_id=request.project_id,
                    domain=request.domain,
                    workflow_name=request.workflow_name or "default"
                )
            
            # Generate workflow name if not provided
            workflow_name = request.workflow_name or f"feature_workflow_{request.project_id}_{request.domain}"
            
            # Generate workflow description if not provided
            workflow_description = request.workflow_description or f"Feature workflow for {request.project_id} in {request.domain} domain"
            
            # Determine save path
            if request.save_path:
                save_path = Path(request.save_path)
            else:
                # Generate default filename with version
                safe_name = workflow_name.replace(" ", "_").replace("/", "_")
                filename = f"{safe_name}_v{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                save_path = self._save_directory / "finalized" / filename
            
            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare finalized workflow data
            finalized_workflow = {
                "workflow_metadata": {
                    "name": workflow_name,
                    "description": workflow_description,
                    "type": request.workflow_type or "feature_registry",
                    "version": version,
                    "project_id": request.project_id,
                    "domain": request.domain,
                    "finalized_at": datetime.now().isoformat(),
                    "finalized_by": request.query_id  # Could be user_id in production
                },
                "conversations": {
                    "total_queries": len(context.previous_queries),
                    "queries": context.previous_queries,
                    "compliance_framework": context.compliance_framework,
                    "severity_levels": context.severity_levels,
                    "sla_requirements": context.sla_requirements
                },
                "selected_features": {
                    "total_count": len(selected_entries),
                    "features": [self._feature_to_dict(entry) for entry in selected_entries]
                },
                "feature_registry": {
                    "total_features": len(context.feature_registry),
                    "all_features": [self._feature_to_dict(entry) for entry in context.feature_registry.values()]
                },
                "pipeline_structure": {
                    "bronze_to_silver": [
                        {
                            "feature_id": entry.feature_id,
                            "feature_name": entry.feature_name,
                            "silver_pipeline": entry.silver_pipeline
                        }
                        for entry in selected_entries
                        if entry.silver_pipeline
                    ],
                    "silver_to_gold": [
                        {
                            "feature_id": entry.feature_id,
                            "feature_name": entry.feature_name,
                            "gold_pipeline": entry.gold_pipeline
                        }
                        for entry in selected_entries
                        if entry.gold_pipeline
                    ]
                }
            }
            
            # Save to file
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(finalized_workflow, f, indent=2, default=str)
            
            logger.info(f"Finalized workflow '{workflow_name}' v{version} with {len(selected_entries)} features saved to {save_path}")
            
            return {
                "status": "finished",
                "workflow_name": workflow_name,
                "workflow_description": workflow_description,
                "workflow_type": request.workflow_type or "feature_registry",
                "version": version,
                "total_features": len(selected_entries),
                "save_path": str(save_path),
                "message": f"Finalized workflow '{workflow_name}' v{version} with {len(selected_entries)} features"
            }
            
        except Exception as e:
            logger.error(f"Error handling finalize request: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _get_next_version(
        self,
        project_id: str,
        domain: str,
        workflow_name: str
    ) -> str:
        """Get the next version number for a workflow"""
        try:
            finalized_dir = self._save_directory / "finalized"
            if not finalized_dir.exists():
                return "1.0.0"
            
            # Look for existing versions of this workflow
            safe_name = workflow_name.replace(" ", "_").replace("/", "_")
            pattern = f"{safe_name}_v*.json"
            
            existing_versions = []
            for file_path in finalized_dir.glob(pattern):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get("workflow_metadata", {}).get("name") == workflow_name:
                            version_str = data.get("workflow_metadata", {}).get("version", "1.0.0")
                            existing_versions.append(version_str)
                except:
                    continue
            
            if not existing_versions:
                return "1.0.0"
            
            # Parse versions and find max
            max_version = "1.0.0"
            max_parts = [0, 0, 0]
            
            for version_str in existing_versions:
                try:
                    parts = [int(x) for x in version_str.split(".")]
                    if len(parts) == 3:
                        if parts > max_parts:
                            max_parts = parts
                            max_version = version_str
                except:
                    continue
            
            # Increment patch version
            parts = max_parts
            parts[2] += 1
            return f"{parts[0]}.{parts[1]}.{parts[2]}"
            
        except Exception as e:
            logger.warning(f"Error determining next version, defaulting to 1.0.0: {e}")
            return "1.0.0"
    
    async def _process_request_impl_with_streaming(
        self,
        request: FeatureConversationRequest,
        stream_callback
    ):
        """Process request with streaming updates"""
        try:
            # Ensure pipeline is initialized
            await self._ensure_pipeline_initialized()
            
            # Register with streaming manager
            await streaming_manager.register(request.query_id)
            
            # Send initial status
            await stream_callback({
                "query_id": request.query_id,
                "status": "processing",
                "action": request.action,
                "message": f"Processing {request.action} request..."
            })
            
            if request.action == "recommend":
                # Stream feature recommendation process
                await stream_callback({
                    "query_id": request.query_id,
                    "status": "recommending",
                    "message": "Analyzing your query and generating feature recommendations..."
                })
                
                # Get conversation context
                context = self._pipeline.get_conversation_context(
                    request.project_id,
                    request.domain
                )
                
                # Create recommendation request
                recommendation_request = FeatureRecommendationRequest(
                    user_query=request.user_query,
                    project_id=request.project_id,
                    domain=request.domain,
                    conversation_context=context,
                    include_risk_features=True,
                    include_impact_features=True,
                    include_likelihood_features=True
                )
                
                # Stream updates during recommendation
                await stream_callback({
                    "query_id": request.query_id,
                    "status": "analyzing",
                    "message": "Analyzing requirements and identifying relevant features..."
                })
                
                # Get recommendations (this may take time)
                response = await self._pipeline.recommend_features(recommendation_request)
                
                if not response.success:
                    await stream_callback({
                        "query_id": request.query_id,
                        "status": "error",
                        "error": response.error
                    })
                    return
                
                # Stream feature recommendations as they're ready
                features = [self._feature_to_dict(f) for f in response.recommended_features]
                
                # Include cache metadata
                metadata = response.metadata or {}
                new_count = metadata.get("new_features_count", len(features))
                existing_count = metadata.get("existing_features_count", 0)
                total_in_registry = metadata.get("total_in_registry", len(features))
                selected_used = metadata.get("selected_features_used", 0)
                selected_names = metadata.get("selected_feature_names", [])
                
                # Send features in batches for better UX
                batch_size = 5
                for i in range(0, len(features), batch_size):
                    batch = features[i:i + batch_size]
                    await stream_callback({
                        "query_id": request.query_id,
                        "status": "recommending",
                        "recommended_features": batch,
                        "total_found": len(features),
                        "current_batch": i // batch_size + 1,
                        "total_batches": (len(features) + batch_size - 1) // batch_size,
                        "new_features_count": new_count,
                        "existing_features_count": existing_count,
                        "selected_features_used": selected_used
                    })
                    # Small delay for better UX
                    await asyncio.sleep(0.1)
                
                # Send final update
                message = f"Generated {len(features)} feature recommendations"
                if new_count > 0 and existing_count > 0:
                    message += f" ({new_count} new, {existing_count} from cache)"
                elif existing_count > 0:
                    message += f" (all from cache)"
                if selected_used > 0:
                    message += f" - Built upon {selected_used} previously selected features"
                
                await stream_callback({
                    "query_id": request.query_id,
                    "status": "finished",
                    "recommended_features": features,
                    "total_found": len(features),
                    "conversation_context": self._context_to_dict(response.conversation_context),
                    "message": message,
                    "metadata": {
                        "new_features_count": new_count,
                        "existing_features_count": existing_count,
                        "total_in_registry": total_in_registry,
                        "selected_features_used": selected_used,
                        "selected_feature_names": selected_names
                    }
                })
                
            elif request.action == "select":
                await stream_callback({
                    "query_id": request.query_id,
                    "status": "selecting",
                    "message": "Selecting features and storing in cache..."
                })
                
                result = await self._handle_select(request)
                
                if result.get("status") == "finished" and request.auto_save:
                    await stream_callback({
                        "query_id": request.query_id,
                        "status": "saving",
                        "message": "Saving selected features to file..."
                    })
                
                await stream_callback({
                    "query_id": request.query_id,
                    **result
                })
                
            elif request.action == "save":
                await stream_callback({
                    "query_id": request.query_id,
                    "status": "saving",
                    "message": "Saving selected features to file..."
                })
                
                result = await self._handle_save(request)
                
                await stream_callback({
                    "query_id": request.query_id,
                    **result
                })
            
            elif request.action == "finalize":
                await stream_callback({
                    "query_id": request.query_id,
                    "status": "finalizing",
                    "message": "Finalizing workflow and creating versioned snapshot..."
                })
                
                result = await self._handle_finalize(request)
                
                await stream_callback({
                    "query_id": request.query_id,
                    **result
                })
            
        except Exception as e:
            logger.error(f"Error in streaming request processing: {e}", exc_info=True)
            await stream_callback({
                "query_id": request.query_id,
                "status": "error",
                "error": str(e)
            })
        finally:
            await streaming_manager.close(request.query_id)
    
    def _create_response(
        self,
        event_id: str,
        result: Any
    ) -> FeatureConversationResponse:
        """Create response from processing result"""
        return FeatureConversationResponse(
            query_id=event_id,
            status=result.get("status", "finished"),
            recommended_features=result.get("recommended_features", []),
            selected_features=result.get("selected_features", []),
            total_selected=result.get("total_selected", 0),
            conversation_context=result.get("conversation_context"),
            error=result.get("error"),
            message=result.get("message")
        )
    
    def _feature_to_dict(self, feature: FeatureRegistryEntry) -> Dict[str, Any]:
        """Convert feature registry entry to dictionary"""
        return {
            "feature_id": feature.feature_id,
            "feature_name": feature.feature_name,
            "feature_type": feature.feature_type,
            "natural_language_question": feature.natural_language_question,
            "business_context": feature.business_context,
            "compliance_reasoning": feature.compliance_reasoning,
            "transformation_layer": feature.transformation_layer,
            "feature_group": feature.feature_group,
            "recommendation_score": feature.recommendation_score,
            "required_schemas": feature.required_schemas,
            "required_fields": feature.required_fields,
            "calculation_logic": feature.calculation_logic,
            "status": feature.status.value,
            "silver_pipeline": feature.silver_pipeline,
            "gold_pipeline": feature.gold_pipeline,
            "depends_on": feature.depends_on,
            "created_at": feature.created_at
        }
    
    def _context_to_dict(self, context: Optional[ConversationContext]) -> Optional[Dict[str, Any]]:
        """Convert conversation context to dictionary"""
        if not context:
            return None
        
        return {
            "project_id": context.project_id,
            "domain": context.domain,
            "compliance_framework": context.compliance_framework,
            "severity_levels": context.severity_levels,
            "sla_requirements": context.sla_requirements,
            "previous_queries": context.previous_queries,
            "selected_features": list(context.selected_features),
            "total_features_in_registry": len(context.feature_registry)
        }
    
    def get_conversation_state(
        self,
        project_id: str,
        domain: str = "cybersecurity"
    ) -> Optional[Dict[str, Any]]:
        """Get current conversation state including all cached features"""
        context = self._pipeline.get_conversation_context(project_id, domain)
        if not context:
            return None
        
        # Get all cached features
        all_features = [self._feature_to_dict(entry) for entry in context.feature_registry.values()]
        
        return {
            "project_id": project_id,
            "domain": domain,
            "total_queries": len(context.previous_queries),
            "total_features": len(context.feature_registry),
            "selected_features": len(context.selected_features),
            "compliance_framework": context.compliance_framework,
            "last_query": context.previous_queries[-1] if context.previous_queries else None,
            "all_cached_features": all_features,
            "previous_queries": context.previous_queries
        }
    
    def get_all_cached_features(
        self,
        project_id: str,
        domain: str = "cybersecurity"
    ) -> List[Dict[str, Any]]:
        """Get all cached features for a project/domain"""
        context = self._pipeline.get_conversation_context(project_id, domain)
        if not context:
            return []
        
        return [self._feature_to_dict(entry) for entry in context.feature_registry.values()]
    
    def get_selected_features_from_cache(
        self,
        project_id: str,
        domain: str = "cybersecurity"
    ) -> List[Dict[str, Any]]:
        """Get only selected features from cache"""
        context = self._pipeline.get_conversation_context(project_id, domain)
        if not context:
            return []
        
        selected_entries = [
            context.feature_registry[fid]
            for fid in context.selected_features
            if fid in context.feature_registry
        ]
        
        return [self._feature_to_dict(entry) for entry in selected_entries]
    
    def list_finalized_workflows(
        self,
        project_id: Optional[str] = None,
        domain: Optional[str] = None,
        workflow_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all finalized workflows, optionally filtered by project_id, domain, or workflow_name"""
        try:
            finalized_dir = self._save_directory / "finalized"
            if not finalized_dir.exists():
                return []
            
            workflows = []
            for file_path in finalized_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        metadata = data.get("workflow_metadata", {})
                        
                        # Apply filters
                        if project_id and metadata.get("project_id") != project_id:
                            continue
                        if domain and metadata.get("domain") != domain:
                            continue
                        if workflow_name and metadata.get("name") != workflow_name:
                            continue
                        
                        workflows.append({
                            "file_path": str(file_path),
                            "workflow_name": metadata.get("name"),
                            "workflow_description": metadata.get("description"),
                            "workflow_type": metadata.get("type"),
                            "version": metadata.get("version"),
                            "project_id": metadata.get("project_id"),
                            "domain": metadata.get("domain"),
                            "finalized_at": metadata.get("finalized_at"),
                            "total_features": data.get("selected_features", {}).get("total_count", 0),
                            "total_queries": data.get("conversations", {}).get("total_queries", 0)
                        })
                except Exception as e:
                    logger.warning(f"Error reading finalized workflow file {file_path}: {e}")
                    continue
            
            # Sort by finalized_at (most recent first)
            workflows.sort(key=lambda x: x.get("finalized_at", ""), reverse=True)
            
            return workflows
            
        except Exception as e:
            logger.error(f"Error listing finalized workflows: {e}", exc_info=True)
            return []
    
    def clear_conversation(
        self,
        project_id: str,
        domain: str = "cybersecurity"
    ) -> None:
        """Clear conversation context"""
        self._pipeline.clear_conversation_context(project_id, domain)
        logger.info(f"Cleared conversation for {project_id}/{domain}")

