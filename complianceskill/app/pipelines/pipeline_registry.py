"""
Pipeline Registry for managing async pipelines

Similar to GraphRegistry but specifically for async pipelines that handle user queries
"""
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

from app.pipelines.base import ExtractionPipeline

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for a registered pipeline"""
    pipeline_id: str
    name: str
    description: Optional[str] = None
    pipeline: ExtractionPipeline = None
    category: str = "general"  # general, data, contextual, analysis, etc.
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class PipelineCategoryConfig:
    """Configuration for a pipeline category"""
    category_id: str
    name: str
    description: Optional[str] = None
    pipelines: Dict[str, PipelineConfig] = field(default_factory=dict)
    default_pipeline_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PipelineRegistry:
    """
    Registry for managing async pipelines
    
    Provides centralized management of pipelines that can be accessed
    throughout the application lifecycle.
    
    Usage:
        # At startup
        registry = get_pipeline_registry()
        
        # Register pipeline
        query_pipeline = AsyncQueryPipeline(...)
        await query_pipeline.initialize()
        
        registry.register_pipeline(
            pipeline_id="user_query_pipeline",
            pipeline=query_pipeline,
            name="User Query Pipeline",
            category="query"
        )
        
        # Later, use pipeline
        pipeline = registry.get_pipeline("user_query_pipeline")
        result = await pipeline.run(inputs={"query": "..."})
    """
    
    def __init__(self):
        self._pipelines: Dict[str, PipelineConfig] = {}
        self._categories: Dict[str, PipelineCategoryConfig] = {}
    
    def register_category(
        self,
        category_id: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PipelineCategoryConfig:
        """Register a pipeline category"""
        category = PipelineCategoryConfig(
            category_id=category_id,
            name=name,
            description=description,
            metadata=metadata or {}
        )
        self._categories[category_id] = category
        logger.info(f"Registered pipeline category: {category_id}")
        return category
    
    def register_pipeline(
        self,
        pipeline_id: str,
        pipeline: ExtractionPipeline,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "general",
        version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        set_as_default: bool = False,
        is_active: bool = True
    ) -> PipelineConfig:
        """
        Register a pipeline in the registry
        
        Args:
            pipeline_id: Unique identifier for the pipeline
            pipeline: Pipeline instance
            name: Display name
            description: Pipeline description
            category: Pipeline category (general, data, contextual, etc.)
            version: Pipeline version
            metadata: Additional metadata
            set_as_default: Whether to set as default for category
            is_active: Whether pipeline is active
            
        Returns:
            PipelineConfig instance
        """
        # Ensure category exists
        if category not in self._categories:
            self.register_category(
                category_id=category,
                name=category.replace("_", " ").title(),
                description=f"Category for {category} pipelines"
            )
        
        config = PipelineConfig(
            pipeline_id=pipeline_id,
            name=name or pipeline.name,
            description=description or pipeline.description,
            pipeline=pipeline,
            category=category,
            version=version or pipeline.version,
            metadata=metadata or {},
            is_active=is_active
        )
        
        self._pipelines[pipeline_id] = config
        
        # Add to category
        category_config = self._categories[category]
        category_config.pipelines[pipeline_id] = config
        
        if set_as_default or category_config.default_pipeline_id is None:
            category_config.default_pipeline_id = pipeline_id
        
        logger.info(f"Registered pipeline: {pipeline_id} (category: {category})")
        return config
    
    def get_pipeline(self, pipeline_id: str) -> Optional[ExtractionPipeline]:
        """Get pipeline by ID"""
        config = self._pipelines.get(pipeline_id)
        if config and config.is_active:
            return config.pipeline
        return None
    
    def get_pipeline_config(self, pipeline_id: str) -> Optional[PipelineConfig]:
        """Get pipeline configuration by ID"""
        return self._pipelines.get(pipeline_id)
    
    def get_category_pipeline(
        self,
        category: str,
        pipeline_id: Optional[str] = None
    ) -> Optional[ExtractionPipeline]:
        """
        Get pipeline from a category (uses default if pipeline_id not provided)
        
        Args:
            category: Category ID
            pipeline_id: Optional specific pipeline ID
            
        Returns:
            Pipeline instance or None
        """
        category_config = self._categories.get(category)
        if not category_config:
            return None
        
        if pipeline_id is None:
            pipeline_id = category_config.default_pipeline_id
        
        if pipeline_id is None:
            return None
        
        config = category_config.pipelines.get(pipeline_id)
        if config and config.is_active:
            return config.pipeline
        return None
    
    def list_pipelines(
        self,
        category: Optional[str] = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        List all pipelines or pipelines in a category
        
        Args:
            category: Optional category filter
            active_only: Only return active pipelines
            
        Returns:
            List of pipeline information
        """
        pipelines = self._pipelines.values()
        
        if category:
            pipelines = [p for p in pipelines if p.category == category]
        
        if active_only:
            pipelines = [p for p in pipelines if p.is_active]
        
        return [
            {
                "pipeline_id": p.pipeline_id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "version": p.version,
                "is_active": p.is_active,
                "metadata": p.metadata
            }
            for p in pipelines
        ]
    
    def list_categories(self) -> List[Dict[str, Any]]:
        """List all pipeline categories"""
        return [
            {
                "category_id": c.category_id,
                "name": c.name,
                "description": c.description,
                "pipeline_count": len(c.pipelines),
                "default_pipeline_id": c.default_pipeline_id,
                "metadata": c.metadata
            }
            for c in self._categories.values()
        ]
    
    def unregister_pipeline(self, pipeline_id: str) -> bool:
        """Unregister a pipeline"""
        if pipeline_id not in self._pipelines:
            return False
        
        config = self._pipelines[pipeline_id]
        
        # Remove from category
        category_config = self._categories.get(config.category)
        if category_config and pipeline_id in category_config.pipelines:
            del category_config.pipelines[pipeline_id]
            
            # Update default if needed
            if category_config.default_pipeline_id == pipeline_id:
                category_config.default_pipeline_id = (
                    next(iter(category_config.pipelines.keys()), None)
                    if category_config.pipelines else None
                )
        
        del self._pipelines[pipeline_id]
        logger.info(f"Unregistered pipeline: {pipeline_id}")
        return True
    
    def set_pipeline_active(self, pipeline_id: str, is_active: bool) -> bool:
        """Activate or deactivate a pipeline"""
        config = self._pipelines.get(pipeline_id)
        if not config:
            return False
        
        config.is_active = is_active
        config.updated_at = datetime.now()
        logger.info(f"Set pipeline {pipeline_id} active={is_active}")
        return True
    
    async def initialize_all(self) -> Dict[str, Any]:
        """
        Initialize all registered pipelines
        
        Returns:
            Dictionary with initialization results
        """
        logger.info("Initializing all registered pipelines...")
        
        results = {
            "total": len(self._pipelines),
            "initialized": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }
        
        for pipeline_id, config in self._pipelines.items():
            if not config.is_active:
                results["skipped"] += 1
                results["details"].append({
                    "pipeline_id": pipeline_id,
                    "status": "skipped",
                    "reason": "inactive"
                })
                continue
            
            try:
                if not config.pipeline.is_initialized:
                    await config.pipeline.initialize()
                    results["initialized"] += 1
                    results["details"].append({
                        "pipeline_id": pipeline_id,
                        "status": "initialized"
                    })
                    logger.info(f"  ✓ Initialized pipeline: {pipeline_id}")
                else:
                    results["skipped"] += 1
                    results["details"].append({
                        "pipeline_id": pipeline_id,
                        "status": "skipped",
                        "reason": "already_initialized"
                    })
                    logger.info(f"  - Pipeline already initialized: {pipeline_id}")
                    
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "pipeline_id": pipeline_id,
                    "status": "failed",
                    "error": str(e)
                })
                logger.error(f"  ✗ Failed to initialize pipeline {pipeline_id}: {str(e)}")
        
        logger.info(f"Pipeline initialization complete: {results['initialized']} initialized, "
                   f"{results['failed']} failed, {results['skipped']} skipped")
        
        return results
    
    async def cleanup_all(self) -> Dict[str, Any]:
        """
        Clean up all registered pipelines
        
        Returns:
            Dictionary with cleanup results
        """
        logger.info("Cleaning up all registered pipelines...")
        
        results = {
            "total": len(self._pipelines),
            "cleaned_up": 0,
            "failed": 0,
            "details": []
        }
        
        for pipeline_id, config in self._pipelines.items():
            try:
                if config.pipeline.is_initialized:
                    await config.pipeline.cleanup()
                    results["cleaned_up"] += 1
                    results["details"].append({
                        "pipeline_id": pipeline_id,
                        "status": "cleaned_up"
                    })
                    logger.info(f"  ✓ Cleaned up pipeline: {pipeline_id}")
                    
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "pipeline_id": pipeline_id,
                    "status": "failed",
                    "error": str(e)
                })
                logger.error(f"  ✗ Failed to clean up pipeline {pipeline_id}: {str(e)}")
        
        logger.info(f"Pipeline cleanup complete: {results['cleaned_up']} cleaned up, "
                   f"{results['failed']} failed")
        
        return results


# Global pipeline registry instance
_global_pipeline_registry = PipelineRegistry()


def get_pipeline_registry() -> PipelineRegistry:
    """Get the global pipeline registry"""
    return _global_pipeline_registry
