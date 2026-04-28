from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select
from app.core.settings import get_settings, Settings
import json
from enum import Enum
import traceback
from app.models.workflowmodels import SharingPermission
from app.core.dependencies import build_document_store, DocumentVectorStore
from langchain_core.documents import Document as LangchainDocument


settings = get_settings()


class BaseService:
    """Base service class with common functionality for all services"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._vs_cache: Dict[str, DocumentVectorStore] = {}
        
    # async def _check_user_permission(
    #     self, 
    #     user_id: UUID, 
    #     resource_type: str, 
    #     resource_id: UUID, 
    #     action: str
    # ) -> bool:
    #     """Check if user has permission to perform action on resource"""
    #     from app.models.rbac import Role, Permission, user_roles
        
    #     # Check system roles first (superuser, system_admin)
    #     stmt = select(Role).join(user_roles).where(
    #         and_(
    #             user_roles.c.user_id == user_id,
    #             Role.role_type == "system",
    #             Role.name.in_(["superuser", "system_admin","user"])
    #         )
    #     )
    #     result = await self.db.execute(stmt)
    #     user_system_roles = result.scalars().all()
        
    #     if user_system_roles:
    #         return True
    #     print(f"I am after user_system_roles")    
    #     # Check resource-specific permissions
    #     permission_stmt = select(Permission).join(
    #         Role.permissions
    #     ).join(
    #         user_roles,
    #         Role.id == user_roles.c.role_id
    #     ).where(
    #         and_(
    #             user_roles.c.user_id == user_id,
    #             or_(
    #                 user_roles.c.object_id == resource_id,
    #                 user_roles.c.object_id.is_(None)  # Global permissions
    #             ),
    #             Permission.resource_type == resource_type,
    #             Permission.action == action
    #         )
    #     )
    #     print("I am after permission")
    #     result = await self.db.execute(permission_stmt)
    #     return result.scalar_one_or_none() is not None
    

    async def _check_user_permission(
    self, 
    user_id: UUID, 
    resource_type: str, 
    resource_id: UUID, 
    action: str
) -> bool:
        """Check if user has permission to perform action on resource"""
        
        try:
            from app.models.rbac import Role, Permission, user_roles
            # Check system roles first (superuser, system_admin, user)
            stmt = select(Role).join(user_roles).where(
                and_(
                    user_roles.c.user_id == user_id,
                    Role.role_type.in_(["system", "external"]),
                    Role.name.in_(["superuser", "system_admin", "user"])
                )
            )
            result = await self.db.execute(stmt)
            user_system_roles = result.scalars().all()
            print(f"user_system_roles is {user_system_roles}")

            if user_system_roles:
                return True
            
            print("I am after user_system_roles")

        except Exception:
            print("Error while checking system roles:")
            traceback.print_exc()
            return False  # You may choose to raise or return False

        try:
            # Check resource-specific permissions
            permission_stmt = select(Permission).join(
                Role.permissions
            ).join(
                user_roles,
                Role.id == user_roles.c.role_id
            ).where(
                and_(
                    user_roles.c.user_id == user_id,
                    or_(
                        user_roles.c.object_id == resource_id,
                        user_roles.c.object_id.is_(None)  # Global permissions
                    ),
                    Permission.resource_type == resource_type,
                    Permission.action == action
                )
            )

            print("I am after permission")

            result = await self.db.execute(permission_stmt)
            result=result.scalar_one_or_none() is not None
            print(f"result is {result}")
            return result

        except Exception:
            print("Error while checking resource-specific permissions:")
            traceback.print_exc()
            return False  # You may choose to raise or return False

    async def _get_user_accessible_resources(
        self,
        user_id: UUID,
        resource_type: str,
        workspace_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None
    ) -> List[UUID]:
        """Get list of resource IDs user has access to"""
        from app.models.workspace import WorkspaceAccess, ProjectAccess
        from app.models.team import team_memberships
        
        accessible_ids = []
        
        # Get workspace access
        if workspace_id:
            stmt = select(WorkspaceAccess).where(
                and_(
                    WorkspaceAccess.workspace_id == workspace_id,
                    WorkspaceAccess.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            workspace_access = result.scalar_one_or_none()
            if workspace_access:
                accessible_ids.append(workspace_id)
        
        # Get project access
        if project_id:
            stmt = select(ProjectAccess).where(
                and_(
                    ProjectAccess.project_id == project_id,
                    ProjectAccess.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            project_access = result.scalar_one_or_none()
            if project_access:
                accessible_ids.append(project_id)
        
        # Get team-based access
        stmt = select(team_memberships.c.team_id).where(
            team_memberships.c.user_id == user_id
        )
        result = await self.db.execute(stmt)
        user_teams = result.all()
        accessible_ids.extend([team_id for (team_id,) in user_teams])
        
        return accessible_ids
    
    def _get_vector_store(self, collection_name: str) -> DocumentVectorStore:
        if collection_name not in self._vs_cache:
            self._vs_cache[collection_name] = build_document_store(collection_name)
        return self._vs_cache[collection_name]

    async def _add_to_chroma(
        self,
        collection_name: str,
        document_id: str,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
    ):
        store = self._get_vector_store(collection_name)
        text = json.dumps(content, default=str)
        doc = LangchainDocument(page_content=text, metadata={**metadata, "id": document_id})
        store.add_documents([doc])

    async def _update_chroma(
        self,
        collection_name: str,
        document_id: str,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
    ):
        store = self._get_vector_store(collection_name)
        try:
            store.vectorstore.delete(ids=[document_id])
        except Exception:
            pass
        text = json.dumps(content, default=str)
        doc = LangchainDocument(page_content=text, metadata={**metadata, "id": document_id})
        store.add_documents([doc])

    async def _delete_from_chroma(self, collection_name: str, document_id: str):
        store = self._get_vector_store(collection_name)
        try:
            store.vectorstore.delete(ids=[document_id])
        except Exception:
            pass

    async def _search_chroma(
        self,
        collection_name: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        store = self._get_vector_store(collection_name)
        raw = store.semantic_search(query, k=limit, where=filters or {})
        return [
            {
                "id": r.get("id"),
                "document": r.get("content"),
                "metadata": r.get("metadata"),
                "distance": r.get("score"),
            }
            for r in raw
        ]