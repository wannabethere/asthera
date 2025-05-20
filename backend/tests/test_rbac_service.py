import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class RBACTestService:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.headers = {}
        self.email = os.getenv("TEST_USER_EMAIL", "test@example.com")
        self.password = os.getenv("TEST_USER_PASSWORD", "testpassword123")

    async def login(self, username: str, password: str) -> bool:
        """Login and get JWT token"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/auth/login",
                    data={
                        "email": self.email,
                        "password": self.password
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.token = data.get("access_token")
                        self.headers = {
                            "Authorization": f"Bearer {self.token}",
                            "Content-Type": "application/json"
                        }
                        print(f"Successfully logged in as {username}")
                        return True
                    else:
                        print(f"Login failed: {await response.text()}")
                        return False
        except Exception as e:
            print(f"Login error: {str(e)}")
            return False

    async def create_permission(self, name: str, resource_type: str, action: str, description: Optional[str] = None) -> Dict:
        """Create a new permission"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/rbac/permissions",
                    headers=self.headers,
                    json={
                        "name": name,
                        "description": description,
                        "resource_type": resource_type,
                        "action": action
                    }
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to create permission: {await response.text()}")
                        return {}
        except Exception as e:
            print(f"Error creating permission: {str(e)}")
            return {}

    async def create_role(self, name: str, permission_ids: List[str], description: Optional[str] = None) -> Dict:
        """Create a new role with permissions"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/rbac/roles",
                    headers=self.headers,
                    json={
                        "name": name,
                        "description": description,
                        "permission_ids": permission_ids
                    }
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to create role: {await response.text()}")
                        return {}
        except Exception as e:
            print(f"Error creating role: {str(e)}")
            return {}

    async def assign_roles_to_user(self, user_id: str, role_ids: List[str]) -> List[Dict]:
        """Assign roles to a user"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/rbac/users/{user_id}/roles",
                    headers=self.headers,
                    json={"role_ids": role_ids}
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to assign roles: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Error assigning roles: {str(e)}")
            return []

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """Get permissions for a user"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v1/rbac/users/{user_id}/permissions",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("permissions", [])
                    else:
                        print(f"Failed to get permissions: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Error getting permissions: {str(e)}")
            return []

    async def get_user_roles(self, user_id: str) -> List[Dict]:
        """Get roles for a user"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v1/rbac/users/{user_id}/roles",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to get user roles: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Error getting user roles: {str(e)}")
            return []

    async def list_all_permissions(self) -> List[Dict]:
        """List all available permissions"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v1/rbac/permissions",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to list permissions: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Error listing permissions: {str(e)}")
            return []

    async def list_all_roles(self) -> List[Dict]:
        """List all available roles"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v1/rbac/roles",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to list roles: {await response.text()}")
                        return []
        except Exception as e:
            print(f"Error listing roles: {str(e)}")
            return []

async def main():
    # Initialize the service
    service = RBACTestService()
    
    # Login with superuser credentials
    if not await service.login(service.email, service.password):
        print("Failed to login. Exiting...")
        return

    # List all permissions and roles
    permissions = await service.list_all_permissions()
    print(f"Available permissions: {json.dumps(permissions, indent=2)}")

    roles = await service.list_all_roles()
    print(f"Available roles: {json.dumps(roles, indent=2)}")

    # Get current user's roles and permissions
    user_id = "current"  # or specific user ID
    user_roles = await service.get_user_roles(user_id)
    print(f"User roles: {json.dumps(user_roles, indent=2)}")

    user_permissions = await service.get_user_permissions(user_id)
    print(f"User permissions: {user_permissions}")

if __name__ == "__main__":
    asyncio.run(main()) 