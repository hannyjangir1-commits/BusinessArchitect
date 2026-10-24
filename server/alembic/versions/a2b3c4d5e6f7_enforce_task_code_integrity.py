"""Enforce project-scoped roadmap task code integrity and uniqueness.

Revision ID: a2b3c4d5e6f7
Revises: f1a8b9c0d1e2
Create Date: 2026-10-24 22:00:00.000000

"""
from typing import Sequence, Union
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from alembic import context

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f1a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_offline = context.is_offline_mode()

    if not is_offline and conn is not None:
        # 1. Detect duplicate task codes per project
        dup_query = text("""
            SELECT project_id, task_code, COUNT(*) as cnt
            FROM roadmap_tasks
            GROUP BY project_id, task_code
            HAVING COUNT(*) > 1
        """)
        duplicates = conn.execute(dup_query).fetchall()

        for dup in duplicates:
            proj_id = dup[0]
            code = dup[1]

            # Fetch all tasks in this project to check dependencies
            all_proj_tasks = conn.execute(
                text("SELECT id, task_code, dependencies FROM roadmap_tasks WHERE project_id = :p"),
                {"p": proj_id}
            ).fetchall()

            # Check if any task references this duplicate code in its dependencies
            is_referenced = False
            referencing_tasks = []
            for row in all_proj_tasks:
                deps_raw = row[2]
                if deps_raw:
                    if isinstance(deps_raw, str):
                        try:
                            deps_list = json.loads(deps_raw)
                        except Exception:
                            deps_list = []
                    elif isinstance(deps_raw, list):
                        deps_list = deps_raw
                    else:
                        deps_list = []
                    if code in deps_list:
                        is_referenced = True
                        referencing_tasks.append(row[1])

            if is_referenced:
                # Ambiguous case: cannot determine which physical task row was intended as prerequisite.
                # Must abort migration cleanly, leaving existing data intact.
                raise RuntimeError(
                    f"Preflight migration failed: Ambiguous duplicate task code '{code}' in project '{proj_id}' "
                    f"is referenced by downstream tasks ({', '.join(referencing_tasks)}). "
                    "Manual resolution required before applying unique constraint."
                )

            # Unambiguous case: duplicate is unreferenced by dependencies.
            # Deterministically renumber duplicate rows (preserve row 0, renumber rows 1..N).
            dup_rows = conn.execute(
                text("""
                    SELECT id, created_at
                    FROM roadmap_tasks
                    WHERE project_id = :p AND task_code = :c
                    ORDER BY created_at ASC, id ASC
                """),
                {"p": proj_id, "c": code}
            ).fetchall()

            existing_codes = {r[1] for r in all_proj_tasks}

            for idx, r in enumerate(dup_rows[1:], start=1):
                row_id = r[0]
                new_code = f"{code}_dup{idx}"
                counter = idx
                while new_code in existing_codes:
                    counter += 1
                    new_code = f"{code}_dup{counter}"
                existing_codes.add(new_code)
                conn.execute(
                    text("UPDATE roadmap_tasks SET task_code = :nc WHERE id = :rid"),
                    {"nc": new_code, "rid": row_id}
                )

    # 2. Add UniqueConstraint to roadmap_tasks(project_id, task_code)
    with op.batch_alter_table('roadmap_tasks', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_roadmap_tasks_project_task_code',
            ['project_id', 'task_code']
        )


def downgrade() -> None:
    with op.batch_alter_table('roadmap_tasks', schema=None) as batch_op:
        batch_op.drop_constraint('uq_roadmap_tasks_project_task_code', type_='unique')
