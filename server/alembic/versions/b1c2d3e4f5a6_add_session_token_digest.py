"""Add token_digest to sessions and make session_token nullable.

Revision ID: b1c2d3e4f5a6
Revises: a2b3c4d5e6f7
Create Date: 2026-10-25 04:45:00.000000

"""
from typing import Sequence, Union
import hashlib
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from alembic import context

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    is_offline = context.is_offline_mode()
    conn = op.get_bind()

    # 1. Add token_digest column and alter session_token to nullable using batch_alter_table
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token_digest', sa.String(length=64), nullable=True))
        batch_op.alter_column('session_token', existing_type=sa.String(length=128), nullable=True)

    # 2. Backfill existing active sessions: hash raw session_token to token_digest
    if not is_offline and conn is not None:
        rows = conn.execute(
            text("SELECT id, session_token FROM sessions WHERE token_digest IS NULL AND session_token IS NOT NULL")
        ).fetchall()
        for row in rows:
            sess_id, raw_token = row[0], row[1]
            if raw_token:
                digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                conn.execute(
                    text("UPDATE sessions SET token_digest = :digest WHERE id = :id"),
                    {"digest": digest, "id": sess_id}
                )

    # 3. Create unique index on token_digest
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index('ix_sessions_token_digest', ['token_digest'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index('ix_sessions_token_digest')
        batch_op.drop_column('token_digest')
        batch_op.alter_column('session_token', existing_type=sa.String(length=128), nullable=True)
