import logging
import traceback
from typing import List, Dict, Any, Optional
from app.core.session_manager import SessionManager
from sqlalchemy import select, and_, or_, Table, MetaData
from sqlalchemy.orm import joinedload
from httpx import AsyncClient
from pydantic import BaseModel, Field
from enum import Enum
from fastapi import HTTPException
from app.schemas.dbmodels import SharePermission,Domain
import traceback
from app.service.models import ShareInfo, PermissionLevel,EntityType
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




class ActionType(str, Enum):
    view = "view"
    create = "create"
    update = "update"
    delete = "delete"
    manage_permissions = "manage_permissions"
    add_tables = "add_tables"

class SharePermissions:
    # CLASS VARIABLES for caching - shared across all instances
    _user_cache = {}
    _system_info_cache = {}
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.genai_client = AsyncClient()
        self.genai_url = "https://eanalyticsapi.phenomecloud.com/"
        self.metadata = MetaData()
        
        # Permission definitions with actions mapping
        self.permissions = {
            "permissions": [
                {
                    "permission_name": "read",
                    "permission_description": "Can view data but cannot modify it.",
                    "actions": [ActionType.view]
                },
                {
                    "permission_name": "read_write", 
                    "permission_description": "Can view and modify data.",
                    "actions": [ActionType.view, ActionType.create, ActionType.update, ActionType.add_tables]
                },
                {
                    "permission_name": "admin",
                    "permission_description": "Full access to all data and settings.",
                    "actions": [ActionType.view, ActionType.create, ActionType.update, ActionType.delete, ActionType.manage_permissions, ActionType.add_tables]
                }
            ]
        }

    async def _validate_user(self, token: str) -> Dict[str, Any]:
        """Validate user token and return user information with caching"""
        if token in SharePermissions._user_cache:
            return SharePermissions._user_cache[token]
            
        try:
            response = await self.genai_client.post(
                f"{self.genai_url}/api/v1/auth/validate-session", 
                params={"token": token}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
                
            response_data = response.json()
            if not response_data.get("is_valid"):
                raise HTTPException(status_code=401, detail="Invalid token")
                
            user = response_data.get('user')
            SharePermissions._user_cache[token] = user  # Cache in class variable
            return user
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise HTTPException(status_code=500, detail="Token validation failed")

    async def _get_user_complete_info(self, token: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """Get complete user information with caching"""
        if token in SharePermissions._system_info_cache:
            return SharePermissions._system_info_cache[token]
            
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = await self.genai_client.get(
                f"{self.genai_url}/api/v1/users/system-info", 
                headers=headers
            )
            
            if response.status_code == 200:
                system_info = response.json()
                user_info = {
                    "workspace_ids": [ws.get("id") for ws in system_info.get("workspaces", [])],
                    "project_ids": [proj.get("id") for proj in system_info.get("projects", [])],
                    "team_ids": [team.get("id") for team in system_info.get("teams", [])]
                }
                SharePermissions._system_info_cache[token] = user_info  # Cache in class variable
                return user_info
            else:
                return {"workspace_ids": [], "project_ids": [], "team_ids": []}
                
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {"workspace_ids": [], "project_ids": [], "team_ids": []}

    def _is_higher_permission(self, perm1: str, perm2: str) -> bool:
        """Check if perm1 is higher than perm2"""
        hierarchy = {"read": 1, "read_write": 2, "admin": 3}
        return hierarchy.get(perm1, 0) > hierarchy.get(perm2, 0)

    def _check_action_allowed(self, permission_level: str, action: ActionType) -> bool:
        """Check if action is allowed for given permission level"""
        for perm in self.permissions["permissions"]:
            if perm["permission_name"] == permission_level:
                return action in perm["actions"]
        return False

    async def get_share_datamodel_info(self, token: str) -> Dict[str, Any]:
        """Get all shareable entities and permissions info"""
        try:
            user = await self._validate_user(token)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get system info (this will be cached in class variable)
            response = await self.genai_client.get(
                f"{self.genai_url}/api/v1/users/system-info", 
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to get system info")
            
            system_info = response.json()
            
            response = await self.genai_client.get(
                f"{self.genai_url}/api/v1/users/getAllUsers", 
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to get users")
            
            all_users = response.json()
                
            return {
                    "viewable_users": all_users,
                    "viewable_workspaces": system_info.get("workspaces", []),
                    "viewable_projects": system_info.get("projects", []),
                    "viewable_teams": system_info.get("teams", []),
                    "permissions": self.permissions
                }
                
        except HTTPException:
            traceback.print_exc()
            raise
        except Exception as e:
            logger.error(f"Error in get_share_datamodel_info: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve share information")

    async def store_info(self, token: str, share_info: ShareInfo, domain_id: str) -> Dict[str, Any]:
        """Store sharing permission information"""
        try:
            user = await self._validate_user(token)
            
            # Check permission first
            permission_check = await self.check_user_permission(token, domain_id)
            if not permission_check["has_permission"]:
                raise HTTPException(status_code=403, detail="No permission to manage sharing")
            
            async with self.session_manager.get_async_db_session() as session:
                share_permission = SharePermission(
                    entity_id=share_info.entity_id,
                    domain_id=domain_id,
                    shared_with=share_info.entity_type.value,
                    permission=share_info.permission.value,
                    shared_by=user.get("id"),
                    created_by=user.get("id"),
                    modified_by=user.get("id"),
                )

                session.add(share_permission)
                await session.commit()
                await session.refresh(share_permission)
                
                return {
                    "message": "Permission shared successfully",
                    "share_permission_id": share_permission.share_permission_id,
                    "domain_id": domain_id,
                    "entity_id": share_info.entity_id,
                    "entity_type": share_info.entity_type.value,
                    "permission": share_info.permission.value,
                    "shared_by": user.get("id")
                }
                
        except HTTPException:
            traceback.print_exc()
            raise
        except Exception as e:
            logger.error(f"Error in store_info: {e}")
            raise HTTPException(status_code=500, detail="Failed to store share information")

    async def get_user_domains(self, token: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all datasets created by or accessible to user"""
        try:
            user = await self._validate_user(token)
            target_user_id = user_id or user.get("id")
            
            async with self.session_manager.get_async_db_session() as session:
                # Get owned domains with datasets using ORM
                owned_result = await session.execute(
                    select(Domain).options(joinedload(Domain.datasets)).where(Domain.created_by == target_user_id)
                )
                owned_domains = owned_result.unique().scalars().all()
                
                # Convert to dict and add permission level
                owned_datasets = []
                owned_domain_ids = set()
                for domain in owned_domains:
                    for dataset in domain.datasets:
                        dataset_dict = {
                            "dataset_id": dataset.dataset_id,
                            "name": dataset.name,
                            "display_name": dataset.display_name,
                            "description": dataset.description,
                            "created_by": dataset.created_by,
                            "created_at": dataset.created_at,
                            "permission_level": "admin",
                            "project_info": {
                                "domain_id": domain.domain_id,
                                "domain_name": domain.display_name
                            }
                        }
                        owned_datasets.append(dataset_dict)
                    owned_domain_ids.add(domain.domain_id)
                
                # Get user info and shared datasets
                user_info = await self._get_user_complete_info(token, user)
                entity_ids = [target_user_id] + user_info.get("workspace_ids", []) + user_info.get("project_ids", []) + user_info.get("team_ids", [])
                
                # Get shared domains with datasets with eager loading
                shared_result = await session.execute(
                    select(SharePermission)
                    .options(joinedload(SharePermission.domains).joinedload(Domain.datasets))
                    .where(
                        and_(
                            SharePermission.entity_id.in_(entity_ids),
                            SharePermission.domain_id.notin_(owned_domain_ids)
                        )
                    )
                )
                shared_permissions = shared_result.unique().scalars().all()
                
                # Convert shared datasets
                shared_datasets = []
                for perm in shared_permissions:
                    if perm.domains and perm.domains.datasets:
                        for dataset in perm.domains.datasets:
                            dataset_dict = {
                                "dataset_id": dataset.dataset_id,
                                "name": dataset.name,
                                "display_name": dataset.display_name,
                                "description": dataset.description,
                                "created_by": dataset.created_by,
                                "created_at": dataset.created_at,
                                "permission_level": perm.permission,
                                "shared_by": perm.shared_by,
                                "shared_through": perm.shared_with,
                                "project_info": {
                                    "domain_id": perm.domains.domain_id,
                                    "domain_name": perm.domains.display_name
                                    
                                }
                            }
                            shared_datasets.append(dataset_dict)
                
                return {
                    "my_datasets": owned_datasets,
                    "shared_datasets": shared_datasets,
                    "total_my_datasets": len(owned_datasets),
                    "total_shared_datasets": len(shared_datasets)
                }
                
        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error in get_user_datasets: {e}")
            raise HTTPException(status_code=500, detail="Failed to get user datasets")     
    # async def check_user_permission(self, token: str, domain_id: str, action: ActionType) -> Dict[str, Any]:
    #     """Check if user has permission to perform action on domain"""
    #     try:
    #         user = await self._validate_user(token)
    #         user_id = user.get("id")
            
    #         async with self.session_manager.get_async_db_session() as session:
    #             # Check if user owns the domain using ORM
    #             owner_result = await session.execute(
    #                 select(Domain).where(and_(Domain.domain_id == domain_id, Domain.created_by == user_id))
    #             )
    #             if owner_result.scalar_one_or_none():
    #                 return {"has_permission": True, "permission_level": "admin", "reason": "Owner"}
                
    #             # Check if domain exists
    #             domain_result = await session.execute(select(Domain).where(Domain.domain_id == domain_id))
    #             domain = domain_result.scalar_one_or_none()
                
    #             if not domain:
    #                 return {"has_permission": False, "permission_level": None, "reason": "domain not found"}
                
    #             # Get user's group memberships and check shared permissions
    #             user_info = await self._get_user_complete_info(token, user)
    #             entity_ids = [user_id] + user_info.get("workspace_ids", []) + user_info.get("project_ids", []) + user_info.get("team_ids", [])
                
    #             perm_result = await session.execute(
    #                 select(SharePermission.permission).where(
    #                     and_(
    #                         SharePermission.domain_id == domain_id,
    #                         SharePermission.entity_id.in_(entity_ids)
    #                     )
    #                 )
    #             )
                
    #             permissions = [row.permission for row in perm_result.fetchall()]
    #             if not permissions:
    #                 return {"has_permission": False, "permission_level": None, "reason": "No permission"}
                
    #             # Get highest permission
    #             highest_permission = max(permissions, key=lambda x: {"read": 1, "read_write": 2, "admin": 3}.get(x, 0))
    #             has_permission = self._check_action_allowed(highest_permission, action)
                
    #             return {
    #                 "has_permission": has_permission,
    #                 "permission_level": highest_permission,
    #                 "reason": "Shared"
    #             }
                
    #     except HTTPException:
    #         raise
    #     except Exception as e:
    #         logger.error(f"Permission check failed: {e}")
    #         raise HTTPException(status_code=500, detail="Permission check failed")


    async def check_user_permission(self, token: str, domain_id: str) -> Dict[str, Any]:
        """Check user's permission level for domain"""
        try:
            user = await self._validate_user(token)
            user_id = user.get("id")
            
            async with self.session_manager.get_async_db_session() as session:
                # Check if user owns the domain using ORM
                owner_result = await session.execute(
                    select(Domain).where(and_(Domain.domain_id == domain_id, Domain.created_by == user_id))
                )
                if owner_result.scalar_one_or_none():
                    return {"has_permission": True, "permission_level": "admin", "reason": "Owner"}
                
                # Check if domain exists
                domain_result = await session.execute(select(Domain).where(Domain.domain_id == domain_id))
                domain = domain_result.scalar_one_or_none()
                
                if not domain:
                    return {"has_permission": False, "permission_level": None, "reason": "domain not found"}
                
                # Get user's group memberships and check shared permissions
                user_info = await self._get_user_complete_info(token, user)
                entity_ids = [user_id] + user_info.get("workspace_ids", []) + user_info.get("project_ids", []) + user_info.get("team_ids", [])
                
                perm_result = await session.execute(
                    select(SharePermission.permission).where(
                        and_(
                            SharePermission.domain_id == domain_id,
                            SharePermission.entity_id.in_(entity_ids)
                        )
                    )
                )
                
                permissions = [row.permission for row in perm_result.fetchall()]
                if not permissions:
                    return {"has_permission": False, "permission_level": None, "reason": "No permission"}
                
                # Get highest permission
                highest_permission = max(permissions, key=lambda x: {"read": 1, "read_write": 2, "admin": 3}.get(x, 0))
                
                return {
                    "has_permission": True,
                    "permission_level": highest_permission,
                    "reason": "Shared"
                }
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            raise HTTPException(status_code=500, detail="Permission check failed")

    async def can_add_tables(self, token: str, domain_id: str) -> Dict[str, Any]:
        """Check if user can add tables to domain"""
        return await self.check_user_permission(token, domain_id, ActionType.add_tables)

    async def can_delete_domain(self, token: str, domain_id: str) -> Dict[str, Any]:
        """Check if user can delete domain"""
        return await self.check_user_permission(token, domain_id, ActionType.delete)

    async def can_manage_permissions(self, token: str, domain_id: str) -> Dict[str, Any]:
        """Check if user can manage permissions for domain"""
        return await self.check_user_permission(token, domain_id, ActionType.manage_permissions)

    async def get_domain_permissions(self, token: str, domain_id: str) -> Dict[str, Any]:
        """Get all permissions for a specific domain"""
        try:
            permission_check = await self.check_user_permission(token, domain_id, ActionType.view)
            if not permission_check["has_permission"]:
                raise HTTPException(status_code=403, detail="No permission to view domain permissions")
            
            async with self.session_manager.get_async_db_session() as session:
                # Get domain info using ORM
                domain_result = await session.execute(select(Domain).where(Domain.domain_id == domain_id))
                domain_info = domain_result.scalar_one_or_none()
                
                if not domain_info:
                    raise HTTPException(status_code=404, detail="Domain not found")
                
                # Get all share permissions for this domain
                perm_result = await session.execute(
                    select(SharePermission).where(SharePermission.domain_id == domain_id)
                )
                permissions_raw = perm_result.scalars().all()
                
                permissions = []
                for perm in permissions_raw:
                    permissions.append({
                        "share_permission_id": perm.share_permission_id,
                        "entity_id": perm.entity_id,
                        "shared_with": perm.shared_with,
                        "permission": perm.permission,
                        "shared_by": perm.shared_by,
                        "created_at": perm.created_at
                    })
                
                return {
                    "domain_id": domain_id,
                    "owner":    domain_info.created_by,
                    "permissions": permissions
                }
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in get_domain_permissions: {e}")
            raise HTTPException(status_code=500, detail="Failed to get domain permissions")

    async def remove_domain_sharing(self, token: str, domain_id: str) -> Dict[str, Any]:
        """Remove all sharing permissions for a domain"""
        try:
            permission_check = await self.check_user_permission(token, domain_id, ActionType.manage_permissions)
            if not permission_check["has_permission"]:
                raise HTTPException(status_code=403, detail="No permission to manage sharing")
            
            async with self.session_manager.get_async_db_session() as session:
                # Delete all share permissions for this domain using ORM
                result = await session.execute(
                    select(SharePermission).where(SharePermission.domain_id == domain_id)
                )
                permissions = result.scalars().all()
                
                if permissions:
                    for perm in permissions:
                        await session.delete(perm)
                    await session.commit()
                    
                    return {"message": "Sharing removed successfully", "domain_id": domain_id}
                else:
                    return {"message": "domain was not shared", "domain_id": domain_id}
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in remove_domain_sharing: {e}")
            raise HTTPException(status_code=500, detail="Failed to remove domain sharing")

    async def update_domain_permission(self, token: str, domain_id: str, new_permission: PermissionLevel) -> Dict[str, Any]:
        """Update permission level for a domain"""
        try:
            permission_check = await self.check_user_permission(token, domain_id, ActionType.manage_permissions)
            if not permission_check["has_permission"]:
                raise HTTPException(status_code=403, detail="No permission to manage sharing")
            
            async with self.session_manager.get_async_db_session() as session:
                # Find and update share permissions using ORM
                result = await session.execute(
                    select(SharePermission).where(SharePermission.domain_id == domain_id)
                )
                permissions = result.scalars().all()
                
                if not permissions:
                    raise HTTPException(status_code=404, detail="No shared permissions found for domain")
                
                updated_count = 0
                for perm in permissions:
                    perm.permission = new_permission.value
                    updated_count += 1
                
                await session.commit()
                
                return {
                    "message": "Permission updated successfully",
                    "domain_id": domain_id,
                    "new_permission": new_permission.value,
                    "updated_permissions": updated_count
                }
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in update_domain_permission: {e}")
            raise HTTPException(status_code=500, detail="Failed to update domain permission")