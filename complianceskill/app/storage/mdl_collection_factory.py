"""
MDL Collection Factory

Factory for selecting MDL collection names based on workflow type.
This allows different workflows (CSOD vs DT/LEEN) to use different collections
while sharing the same retrieval service code.
"""
from typing import Literal, Dict
from app.storage.collections import MDLCollections

WorkflowType = Literal["csod", "leen", "dt"]


class MDLCollectionFactory:
    """
    Factory for getting MDL collection names based on workflow type.
    
    Usage:
        factory = MDLCollectionFactory(workflow_type="csod")
        db_schema_collection = factory.get_db_schema_collection()  # Returns "csod_db_schema"
        
        factory = MDLCollectionFactory(workflow_type="dt")
        db_schema_collection = factory.get_db_schema_collection()  # Returns "leen_db_schema"
    """
    
    # Collection name mappings by workflow type
    COLLECTION_MAP: Dict[WorkflowType, Dict[str, str]] = {
        "csod": {
            "db_schema": MDLCollections.CSOD_DB_SCHEMA,
            "table_description": MDLCollections.CSOD_TABLE_DESCRIPTION,
            "metrics_registry": MDLCollections.CSOD_METRICS_REGISTRY,
            "project_meta": MDLCollections.PROJECT_META,  # Shared for now
            "dashboards": MDLCollections.DASHBOARDS,  # Shared for now, but can be workflow-specific in future
        },
        "leen": {
            "db_schema": MDLCollections.DB_SCHEMA,
            "table_description": MDLCollections.TABLE_DESCRIPTION,
            "metrics_registry": MDLCollections.METRICS_REGISTRY,
            "project_meta": MDLCollections.PROJECT_META,
            "dashboards": MDLCollections.DASHBOARDS,
        },
        "dt": {
            "db_schema": MDLCollections.DB_SCHEMA,
            "table_description": MDLCollections.TABLE_DESCRIPTION,
            "metrics_registry": MDLCollections.METRICS_REGISTRY,
            "project_meta": MDLCollections.PROJECT_META,
            "dashboards": MDLCollections.DASHBOARDS,
        },
    }
    
    def __init__(self, workflow_type: WorkflowType = "dt"):
        """
        Initialize factory with workflow type.
        
        Args:
            workflow_type: "csod" for CSOD workflow, "leen" or "dt" for DT/LEEN workflow
        """
        if workflow_type not in self.COLLECTION_MAP:
            raise ValueError(
                f"Unknown workflow_type: {workflow_type}. "
                f"Must be one of: {list(self.COLLECTION_MAP.keys())}"
            )
        self.workflow_type = workflow_type
        self._collections = self.COLLECTION_MAP[workflow_type]
    
    def get_db_schema_collection(self) -> str:
        """Get database schema collection name for this workflow."""
        return self._collections["db_schema"]
    
    def get_table_description_collection(self) -> str:
        """Get table description collection name for this workflow."""
        return self._collections["table_description"]
    
    def get_metrics_registry_collection(self) -> str:
        """Get metrics registry collection name for this workflow."""
        return self._collections["metrics_registry"]
    
    def get_project_meta_collection(self) -> str:
        """Get project metadata collection name for this workflow."""
        return self._collections["project_meta"]
    
    def get_dashboards_collection(self) -> str:
        """Get dashboards collection name for this workflow."""
        return self._collections["dashboards"]
    
    def get_all_collections(self) -> Dict[str, str]:
        """Get all collection names for this workflow as a dictionary."""
        return self._collections.copy()
    
    @classmethod
    def get_collection_for_workflow(
        cls,
        collection_type: str,
        workflow_type: WorkflowType = "dt"
    ) -> str:
        """
        Get a specific collection name for a workflow type.
        
        Args:
            collection_type: One of "db_schema", "table_description", "metrics_registry", "project_meta", "dashboards"
            workflow_type: "csod", "leen", or "dt"
        
        Returns:
            Collection name string
        """
        if workflow_type not in cls.COLLECTION_MAP:
            raise ValueError(
                f"Unknown workflow_type: {workflow_type}. "
                f"Must be one of: {list(cls.COLLECTION_MAP.keys())}"
            )
        collections = cls.COLLECTION_MAP[workflow_type]
        if collection_type not in collections:
            raise ValueError(
                f"Unknown collection_type: {collection_type}. "
                f"Must be one of: {list(collections.keys())}"
            )
        return collections[collection_type]
