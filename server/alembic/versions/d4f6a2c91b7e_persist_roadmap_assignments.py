"""persist roadmap task assignments and execution details

Revision ID: d4f6a2c91b7e
Revises: c1fa92de3310
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "d4f6a2c91b7e"
down_revision: Union[str, Sequence[str], None] = "c1fa92de3310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Older local installs may have these columns already from create_all/manual
    # schema updates even though alembic_version still points at the prior revision.
    # Adding duplicates through SQLite batch mode creates a circular column ordering
    # error, so inspect first and add only columns that are truly missing.
    columns = (
        sa.Column("assigned_to", sa.String(length=128), nullable=False, server_default="Unassigned"),
        sa.Column("assigned_role", sa.String(length=128), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("is_overloaded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    if context.is_offline_mode():
        # Alembic's SQL-only PostgreSQL compilation has no inspectable connection.
        # Emit the regular fresh-schema additions so portable DDL checks can run.
        for column in columns:
            op.add_column("roadmap_tasks", column)
        return

    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("roadmap_tasks")}
    for column in columns:
        if column.name not in existing_columns:
            op.add_column("roadmap_tasks", column)

    # Normalize partially populated legacy columns before the application relies
    # on their current defaults.
    roadmap_tasks = sa.table(
        "roadmap_tasks",
        sa.column("assigned_to", sa.String(length=128)),
        sa.column("steps", sa.JSON()),
        sa.column("is_overloaded", sa.Boolean()),
    )
    op.execute(
        roadmap_tasks.update()
        .where(sa.or_(roadmap_tasks.c.assigned_to.is_(None), sa.func.trim(roadmap_tasks.c.assigned_to) == ""))
        .values(assigned_to="Unassigned")
    )
    op.execute(roadmap_tasks.update().where(roadmap_tasks.c.steps.is_(None)).values(steps=[]))
    op.execute(roadmap_tasks.update().where(roadmap_tasks.c.is_overloaded.is_(None)).values(is_overloaded=False))


def downgrade() -> None:
    with op.batch_alter_table("roadmap_tasks") as batch_op:
        batch_op.drop_column("is_overloaded")
        batch_op.drop_column("steps")
        batch_op.drop_column("department")
        batch_op.drop_column("assigned_role")
        batch_op.drop_column("assigned_to")
