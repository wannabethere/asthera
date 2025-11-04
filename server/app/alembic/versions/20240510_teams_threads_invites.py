"""
Create users, threads, teams, team_memberships, and invites tables
"""
from alembic import op
import sqlalchemy as sa

revision = '20240510_teams_threads_invites'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.create_table(
        'users',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String, nullable=False, unique=True),
        sa.Column('username', sa.String, unique=True),
        sa.Column('password_hash', sa.String),
        sa.Column('okta_id', sa.String, unique=True),
        sa.Column('first_name', sa.String),
        sa.Column('last_name', sa.String),
        sa.Column('last_login', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'threads',
        sa.Column('id', sa.String, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'teams',
        sa.Column('id', sa.String, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String, nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'team_memberships',
        sa.Column('id', sa.String, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('team_id', sa.String, sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'invites',
        sa.Column('id', sa.String, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('team_id', sa.String, sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('email', sa.String, nullable=False),
        sa.Column('invited_by', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String, server_default=sa.text("'pending'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

def downgrade():
    op.drop_table('invites')
    op.drop_table('team_memberships')
    op.drop_table('teams')
    op.drop_table('threads')
    op.drop_table('users') 