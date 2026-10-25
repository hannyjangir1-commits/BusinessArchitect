"""Add copilot_operations table for durable idempotency and ambiguous failure recovery.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-25 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'copilot_operations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('client_msg_id', sa.String(length=128), nullable=False),
        sa.Column('message_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
        sa.Column('user_message_id', sa.String(length=36), nullable=True),
        sa.Column('assistant_message_id', sa.String(length=36), nullable=True),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assistant_message_id'], ['copilot_messages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_message_id'], ['copilot_messages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'client_msg_id', name='uq_copilot_operations_project_client_msg_id')
    )
    with op.batch_alter_table('copilot_operations', schema=None) as batch_op:
        batch_op.create_index('ix_copilot_operations_created_at', ['created_at'], unique=False)
        batch_op.create_index('ix_copilot_operations_project_id', ['project_id'], unique=False)
        batch_op.create_index('ix_copilot_operations_user_id', ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('copilot_operations', schema=None) as batch_op:
        batch_op.drop_index('ix_copilot_operations_user_id')
        batch_op.drop_index('ix_copilot_operations_project_id')
        batch_op.drop_index('ix_copilot_operations_created_at')
    op.drop_table('copilot_operations')
