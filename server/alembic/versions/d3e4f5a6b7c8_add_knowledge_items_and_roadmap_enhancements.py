"""Add project_knowledge_items, knowledge_links, financial_worksheets, and roadmap enhancement columns.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-10-27 05:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create project_knowledge_items table
    op.create_table(
        'project_knowledge_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('item_type', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='active', nullable=False),
        sa.Column('epistemic_status', sa.String(length=32), server_default='hypothesis', nullable=False),
        sa.Column('source_reference', sa.Text(), nullable=True),
        sa.Column('linked_module', sa.String(length=64), nullable=True),
        sa.Column('metadata_json', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('project_knowledge_items', schema=None) as batch_op:
        batch_op.create_index('ix_project_knowledge_items_project_id', ['project_id'], unique=False)
        batch_op.create_index('ix_project_knowledge_items_item_type', ['item_type'], unique=False)
        batch_op.create_index('ix_project_knowledge_items_created_at', ['created_at'], unique=False)

    # 2. Create knowledge_links table
    op.create_table(
        'knowledge_links',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('target_id', sa.String(length=36), nullable=False),
        sa.Column('relationship', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['project_knowledge_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_id'], ['project_knowledge_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('knowledge_links', schema=None) as batch_op:
        batch_op.create_index('ix_knowledge_links_project_id', ['project_id'], unique=False)
        batch_op.create_index('ix_knowledge_links_source_id', ['source_id'], unique=False)
        batch_op.create_index('ix_knowledge_links_target_id', ['target_id'], unique=False)

    # 3. Create financial_worksheets table
    op.create_table(
        'financial_worksheets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('currency', sa.String(length=8), server_default='USD', nullable=False),
        sa.Column('startup_costs', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('fixed_costs', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('variable_costs', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('revenue_model', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('cash_available', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_financial_worksheets_project_id')
    )
    with op.batch_alter_table('financial_worksheets', schema=None) as batch_op:
        batch_op.create_index('ix_financial_worksheets_project_id', ['project_id'], unique=False)

    # 4. Enhance roadmap_tasks table
    with op.batch_alter_table('roadmap_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('branch_type', sa.String(length=32), server_default='core', nullable=False))
        batch_op.add_column(sa.Column('parent_outcome', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('definition_of_done', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('acceptance_criteria', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('edge_type', sa.String(length=32), server_default='prerequisite', nullable=False))
        batch_op.add_column(sa.Column('roadmap_mode', sa.String(length=32), server_default='execution', nullable=False))

    # 5. Enhance module_contents & module_versions with framework_type
    with op.batch_alter_table('module_contents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('framework_type', sa.String(length=64), server_default='standard', nullable=False))

    with op.batch_alter_table('module_versions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('framework_type', sa.String(length=64), server_default='standard', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('module_versions', schema=None) as batch_op:
        batch_op.drop_column('framework_type')

    with op.batch_alter_table('module_contents', schema=None) as batch_op:
        batch_op.drop_column('framework_type')

    with op.batch_alter_table('roadmap_tasks', schema=None) as batch_op:
        batch_op.drop_column('roadmap_mode')
        batch_op.drop_column('edge_type')
        batch_op.drop_column('acceptance_criteria')
        batch_op.drop_column('definition_of_done')
        batch_op.drop_column('parent_outcome')
        batch_op.drop_column('branch_type')

    with op.batch_alter_table('financial_worksheets', schema=None) as batch_op:
        batch_op.drop_index('ix_financial_worksheets_project_id')
    op.drop_table('financial_worksheets')

    with op.batch_alter_table('knowledge_links', schema=None) as batch_op:
        batch_op.drop_index('ix_knowledge_links_target_id')
        batch_op.drop_index('ix_knowledge_links_source_id')
        batch_op.drop_index('ix_knowledge_links_project_id')
    op.drop_table('knowledge_links')

    with op.batch_alter_table('project_knowledge_items', schema=None) as batch_op:
        batch_op.drop_index('ix_project_knowledge_items_created_at')
        batch_op.drop_index('ix_project_knowledge_items_item_type')
        batch_op.drop_index('ix_project_knowledge_items_project_id')
    op.drop_table('project_knowledge_items')
