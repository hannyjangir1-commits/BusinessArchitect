"""initial_baseline_schema

Revision ID: 199a3ff90b48
Revises: 
Create Date: 2026-10-14 16:35:37.114723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '199a3ff90b48'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to create initial baseline tables if not present."""
    conn = op.get_bind()
    try:
        inspector = sa.inspect(conn)
        existing_tables = inspector.get_table_names() if inspector else []
    except Exception:
        existing_tables = []

    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('username', sa.String(length=64), nullable=False),
            sa.Column('email', sa.String(length=128), nullable=False),
            sa.Column('hashed_password', sa.String(length=256), nullable=False),
            sa.Column('terms_accepted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    if 'sessions' not in existing_tables:
        op.create_table(
            'sessions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('session_token', sa.String(length=128), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_sessions_session_token'), 'sessions', ['session_token'], unique=True)

    if 'projects' not in existing_tables:
        op.create_table(
            'projects',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('stage', sa.String(length=32), nullable=False, server_default='Idea / MVP'),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('industry', sa.String(length=64), nullable=True),
            sa.Column('target_customers', sa.Text(), nullable=True),
            sa.Column('goals', sa.Text(), nullable=True),
            sa.Column('business_context', sa.Text(), nullable=True),
            sa.Column('budget', sa.String(length=64), nullable=True),
            sa.Column('existing_stack', sa.JSON(), nullable=True),
            sa.Column('active_module', sa.String(length=64), nullable=False, server_default='overview'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_projects_user_id'), 'projects', ['user_id'], unique=False)

    if 'module_contents' not in existing_tables:
        op.create_table(
            'module_contents',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('module_type', sa.String(length=64), nullable=False),
            sa.Column('active_version_id', sa.String(length=36), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_module_contents_project_id'), 'module_contents', ['project_id'], unique=False)

    if 'module_versions' not in existing_tables:
        op.create_table(
            'module_versions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('module_content_id', sa.String(length=36), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('version_name', sa.String(length=128), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('change_summary', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['module_content_id'], ['module_contents.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_module_versions_module_content_id'), 'module_versions', ['module_content_id'], unique=False)

    if 'roadmap_tasks' not in existing_tables:
        op.create_table(
            'roadmap_tasks',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('task_code', sa.String(length=32), nullable=False),
            sa.Column('phase', sa.String(length=64), nullable=False),
            sa.Column('title', sa.String(length=256), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('timeline', sa.String(length=32), nullable=False, server_default='30-day'),
            sa.Column('start_date', sa.String(length=32), nullable=False),
            sa.Column('end_date', sa.String(length=32), nullable=False),
            sa.Column('priority', sa.String(length=32), nullable=False, server_default='Medium'),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='Pending'),
            sa.Column('dependencies', sa.JSON(), nullable=False),
            sa.Column('deliverables', sa.Text(), nullable=True),
            sa.Column('effort', sa.String(length=64), nullable=True),
            sa.Column('order_index', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_roadmap_tasks_project_id'), 'roadmap_tasks', ['project_id'], unique=False)

    if 'copilot_messages' not in existing_tables:
        op.create_table(
            'copilot_messages',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('role', sa.String(length=32), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_copilot_messages_project_id'), 'copilot_messages', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('copilot_messages')
    op.drop_table('roadmap_tasks')
    op.drop_table('module_versions')
    op.drop_table('module_contents')
    op.drop_table('projects')
    op.drop_table('sessions')
    op.drop_table('users')
