from app.database import SessionLocal
from app.models.rbac import Permission, Role, SYSTEM_ROLES

# Default permissions for different resource types
DEFAULT_PERMISSIONS = [
    # Workspace permissions
    {'name': 'Create Workspace', 'description': 'Can create new workspaces', 'resource_type': 'workspace', 'action': 'create'},
    {'name': 'Read Workspace', 'description': 'Can view workspace details', 'resource_type': 'workspace', 'action': 'read'},
    {'name': 'Update Workspace', 'description': 'Can modify workspace details', 'resource_type': 'workspace', 'action': 'update'},
    {'name': 'Delete Workspace', 'description': 'Can delete workspaces', 'resource_type': 'workspace', 'action': 'delete'},
    {'name': 'Manage Workspace Access', 'description': 'Can manage workspace access permissions', 'resource_type': 'workspace', 'action': 'manage_access'},

    # Project permissions
    {'name': 'Create Project', 'description': 'Can create new projects', 'resource_type': 'project', 'action': 'create'},
    {'name': 'Read Project', 'description': 'Can view project details', 'resource_type': 'project', 'action': 'read'},
    {'name': 'Update Project', 'description': 'Can modify project details', 'resource_type': 'project', 'action': 'update'},
    {'name': 'Delete Project', 'description': 'Can delete projects', 'resource_type': 'project', 'action': 'delete'},
    {'name': 'Manage Project Access', 'description': 'Can manage project access permissions', 'resource_type': 'project', 'action': 'manage_access'},

    # Thread permissions
    {'name': 'Create Thread', 'description': 'Can create new threads', 'resource_type': 'thread', 'action': 'create'},
    {'name': 'Read Thread', 'description': 'Can view thread details', 'resource_type': 'thread', 'action': 'read'},
    {'name': 'Update Thread', 'description': 'Can modify thread details', 'resource_type': 'thread', 'action': 'update'},
    {'name': 'Delete Thread', 'description': 'Can delete threads', 'resource_type': 'thread', 'action': 'delete'},

    # User permissions
    {'name': 'Create User', 'description': 'Can create new users', 'resource_type': 'user', 'action': 'create'},
    {'name': 'Read User', 'description': 'Can view user details', 'resource_type': 'user', 'action': 'read'},
    {'name': 'Update User', 'description': 'Can modify user details', 'resource_type': 'user', 'action': 'update'},
    {'name': 'Delete User', 'description': 'Can delete users', 'resource_type': 'user', 'action': 'delete'},
    {'name': 'Manage User Roles', 'description': 'Can manage user roles', 'resource_type': 'user', 'action': 'manage_roles'},
]

def init_rbac():
    db = SessionLocal()
    try:
        # Create default permissions
        for perm_data in DEFAULT_PERMISSIONS:
            existing = db.query(Permission).filter(
                Permission.resource_type == perm_data['resource_type'],
                Permission.action == perm_data['action']
            ).first()
            if not existing:
                permission = Permission(**perm_data)
                db.add(permission)
        db.commit()

        # Create system roles
        Role.create_system_roles(db)

        # Get all permissions
        all_permissions = db.query(Permission).all()
        permission_map = {
            f"{p.resource_type}:{p.action}": p for p in all_permissions
        }

        # Assign permissions to system roles
        superuser_role = db.query(Role).filter(Role.name == 'superuser').first()
        admin_role = db.query(Role).filter(Role.name == 'admin').first()
        user_role = db.query(Role).filter(Role.name == 'user').first()

        # Superuser gets all permissions
        superuser_role.permissions = all_permissions

        # Admin gets all permissions except user management
        admin_permissions = [
            p for p in all_permissions
            if p.resource_type != 'user' or p.action in ['read']
        ]
        admin_role.permissions = admin_permissions

        # Regular user gets basic permissions
        user_permissions = [
            permission_map.get('workspace:read'),
            permission_map.get('project:read'),
            permission_map.get('thread:create'),
            permission_map.get('thread:read'),
            permission_map.get('thread:update'),
            permission_map.get('thread:delete'),
        ]
        user_role.permissions = [p for p in user_permissions if p]

        db.commit()
        print("RBAC initialization completed successfully")

    except Exception as e:
        db.rollback()
        print(f"Error during RBAC initialization: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_rbac() 