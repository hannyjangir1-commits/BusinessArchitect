"""Add auth rate limit events table and composite indexes.

Revision ID: f1a8b9c0d1e2
Revises: e6b30f8a2c19
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a8b9c0d1e2"
down_revision = "e6b30f8a2c19"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_rate_limit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_auth_rate_limit_scope_key_created",
        "auth_rate_limit_events",
        ["scope", "key_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_rate_limit_created_at",
        "auth_rate_limit_events",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_auth_rate_limit_created_at", table_name="auth_rate_limit_events")
    op.drop_index("ix_auth_rate_limit_scope_key_created", table_name="auth_rate_limit_events")
    op.drop_table("auth_rate_limit_events")
