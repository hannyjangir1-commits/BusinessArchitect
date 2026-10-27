"""Add copilot_proposals table and owner_attempt_id to copilot_operations.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-10-28 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create copilot_proposals table
    op.create_table(
        'copilot_proposals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('target_module', sa.String(length=64), nullable=False),
        sa.Column('source_version_id', sa.String(length=36), nullable=True),
        sa.Column('source_content_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('framework_type', sa.String(length=64), nullable=True),
        sa.Column('instruction', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('proposed_diff', sa.JSON(), nullable=False),
        sa.Column('proposed_content', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('result_version_id', sa.String(length=36), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_copilot_proposals_project_id', 'copilot_proposals', ['project_id'], unique=False)
    op.create_index('ix_copilot_proposals_user_id', 'copilot_proposals', ['user_id'], unique=False)
    op.create_index('ix_copilot_proposals_created_at', 'copilot_proposals', ['created_at'], unique=False)

    # 2. Add owner_attempt_id to copilot_operations table
    with op.batch_alter_table('copilot_operations') as batch_op:
        batch_op.add_column(sa.Column('owner_attempt_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('copilot_operations') as batch_op:
        batch_op.drop_column('owner_attempt_id')
    op.drop_table('copilot_proposals')
