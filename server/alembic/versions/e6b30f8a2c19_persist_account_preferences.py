"""Persist account display names and personal presentation preferences.

Revision ID: e6b30f8a2c19
Revises: d4f6a2c91b7e
"""
from alembic import context, op
import sqlalchemy as sa

revision = "e6b30f8a2c19"
down_revision = "d4f6a2c91b7e"
branch_labels = None
depends_on = None


def upgrade():
    columns = (
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    existing = set() if context.is_offline_mode() else {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")
    }
    for column in columns:
        if column.name not in existing:
            op.add_column("users", column)


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("preferences")
        batch_op.drop_column("display_name")
