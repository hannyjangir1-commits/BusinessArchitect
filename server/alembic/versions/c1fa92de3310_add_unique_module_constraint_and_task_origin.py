"""add_unique_module_constraint_and_task_origin

Revision ID: c1fa92de3310
Revises: b0be8b6f68be
Create Date: 2026-10-16 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = 'c1fa92de3310'
down_revision: Union[str, Sequence[str], None] = 'b0be8b6f68be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import context

def upgrade() -> None:
    is_offline = context.is_offline_mode()
    conn = op.get_bind()

    # 1. Clean up duplicate module_contents before applying unique constraint (online mode only)
    if not is_offline and conn is not None:
        dup_query = text("""
            SELECT project_id, module_type, COUNT(*) as cnt
            FROM module_contents
            GROUP BY project_id, module_type
            HAVING COUNT(*) > 1
        """)
        duplicates = conn.execute(dup_query).fetchall()

        for dup in duplicates:
            proj_id = dup[0]
            mod_type = dup[1]

            # Fetch all rows for this pair ordered by active_version_id NULLS LAST, created_at DESC
            rows = conn.execute(
                text("""
                    SELECT id, active_version_id
                    FROM module_contents
                    WHERE project_id = :p AND module_type = :m
                    ORDER BY created_at DESC
                """),
                {"p": proj_id, "m": mod_type}
            ).fetchall()

            if len(rows) > 1:
                # Pick the primary row: prioritize one that has active_version_id
                primary = None
                for r in rows:
                    if r[1]:
                        primary = r
                        break
                if not primary:
                    primary = rows[0]

                primary_id = primary[0]
                primary_active_ver = primary[1]

                # Remap versions and delete other rows
                for r in rows:
                    if r[0] != primary_id:
                        dup_id = r[0]
                        dup_active = r[1]
                        # Remap module_versions to point to primary_id
                        conn.execute(
                            text("UPDATE module_versions SET module_content_id = :pri WHERE module_content_id = :dup"),
                            {"pri": primary_id, "dup": dup_id}
                        )
                        # If primary had no active version but duplicate did, adopt it
                        if not primary_active_ver and dup_active:
                            conn.execute(
                                text("UPDATE module_contents SET active_version_id = :ver WHERE id = :pri"),
                                {"ver": dup_active, "pri": primary_id}
                            )
                            primary_active_ver = dup_active

                        # Delete duplicate module_contents row
                        conn.execute(
                            text("DELETE FROM module_contents WHERE id = :dup"),
                            {"dup": dup_id}
                        )

    # 2. Add UniqueConstraint to module_contents(project_id, module_type)
    with op.batch_alter_table('module_contents', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_module_contents_project_module', ['project_id', 'module_type'])

    # 3. Add is_ai_generated column to roadmap_tasks with default False (0) for historical tasks
    with op.batch_alter_table('roadmap_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_ai_generated', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    # 4. Standardize any existing 'Ongoing' tasks to canonical 'In Progress' and ensure legacy tasks are False
    if not is_offline and conn is not None:
        conn.execute(text("UPDATE roadmap_tasks SET status = 'In Progress' WHERE status = 'Ongoing'"))
        conn.execute(text("UPDATE roadmap_tasks SET is_ai_generated = 0 WHERE is_ai_generated IS NULL OR is_ai_generated = 1"))


def downgrade() -> None:
    with op.batch_alter_table('roadmap_tasks', schema=None) as batch_op:
        batch_op.drop_column('is_ai_generated')

    with op.batch_alter_table('module_contents', schema=None) as batch_op:
        batch_op.drop_constraint('uq_module_contents_project_module', type_='unique')
