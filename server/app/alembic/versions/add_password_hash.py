"""add password hash

Revision ID: add_password_hash
Revises: add_rbac_tables
Create Date: 2024-03-19 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_password_hash'
down_revision = 'add_rbac_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Add password_hash column to users table
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=True))

def downgrade():
    # Remove password_hash column from users table
    op.drop_column('users', 'password_hash') 