"""update thread columns

Revision ID: update_thread_columns
Revises: add_password_hash
Create Date: 2024-03-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'update_thread_columns'
down_revision = 'add_password_hash'
branch_labels = None
depends_on = None

def upgrade():
    # Drop existing foreign key constraint
    op.drop_constraint('threads_user_id_fkey', 'threads', type_='foreignkey')
    
    # Drop existing columns
    op.drop_column('threads', 'user_id')
    
    # Add new columns
    op.add_column('threads', sa.Column('description', sa.String(), nullable=True))
    op.add_column('threads', sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('threads', sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('threads', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('threads', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    
    # Make title non-nullable
    op.alter_column('threads', 'title',
               existing_type=sa.String(),
               nullable=False)
    
    # Add foreign key constraints
    op.create_foreign_key('threads_project_id_fkey', 'threads', 'projects', ['project_id'], ['id'])
    op.create_foreign_key('threads_created_by_fkey', 'threads', 'users', ['created_by'], ['id'])
    
    # Make project_id and created_by non-nullable after adding foreign keys
    op.alter_column('threads', 'project_id',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=False)
    op.alter_column('threads', 'created_by',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=False)

def downgrade():
    # Drop foreign key constraints
    op.drop_constraint('threads_project_id_fkey', 'threads', type_='foreignkey')
    op.drop_constraint('threads_created_by_fkey', 'threads', type_='foreignkey')
    
    # Drop new columns
    op.drop_column('threads', 'is_active')
    op.drop_column('threads', 'updated_at')
    op.drop_column('threads', 'created_by')
    op.drop_column('threads', 'project_id')
    op.drop_column('threads', 'description')
    
    # Make title nullable again
    op.alter_column('threads', 'title',
               existing_type=sa.String(),
               nullable=True)
    
    # Add back user_id column
    op.add_column('threads', sa.Column('user_id', sa.String(), nullable=True))
    
    # Add back foreign key constraint
    op.create_foreign_key('threads_user_id_fkey', 'threads', 'users', ['user_id'], ['id'])
    
    # Make user_id non-nullable
    op.alter_column('threads', 'user_id',
               existing_type=sa.String(),
               nullable=False) 