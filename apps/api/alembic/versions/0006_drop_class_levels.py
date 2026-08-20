"""drop class levels — classes are now standalone arms

Revision ID: 0006_drop_class_levels
Revises: 0005_comment_system
Create Date: 2026-08-18

ClassLevel is removed entirely. ClassArm.name is now the full class label
(e.g. "JSS 1A"). Anything that was scoped by ``class_level_id`` is re-scoped by
``class_arm_id``:

* ``class_arms`` — ``name`` is promoted to the full class label (was the arm
  letter like "A"); the level column is dropped.
* ``subject_offerings`` — a per-level offering becomes one row per arm.
* ``lesson_plans`` / ``question_banks`` — each generated cell moves to an arm of
  the same level (first by name); orphan rows (level with no arms) are dropped
  since they are reproducible AI artifacts.
* ``assessment_components`` — level-scoped rows move to an arm of the level.
* ``fee_structures`` — the ``class_level_id`` column is dropped.
* the ``class_levels`` table itself is dropped.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_drop_class_levels"
down_revision: Union[str, None] = "0005_comment_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _attach_to_arm(bind, table: str) -> None:
    """Fill ``class_arm_id`` on ``table`` rows that carry a ``class_level_id`` by
    attaching them to the first arm (by name) of that level. Rows whose level has
    no arms are deleted (they are generated, reproducible artifacts)."""
    orphan_levels = [
        r[0]
        for r in bind.execute(
            sa.text(
                f"SELECT l.id FROM class_levels l "
                f"WHERE NOT EXISTS (SELECT 1 FROM class_arms a WHERE a.class_level_id = l.id)"
            )
        ).fetchall()
    ]
    if orphan_levels:
        bind.execute(
            sa.text(f"DELETE FROM {table} WHERE class_level_id IN :ids").bindparams(
                sa.bindparam(
                    "ids", value=orphan_levels, expanding=True, type_=sa.Uuid()
                )
            )
        )

    rows = bind.execute(
        sa.text(
            f"SELECT {table}.id, {table}.class_level_id, a.id AS arm_id "
            f"FROM {table} "
            f"JOIN class_arms a ON a.class_level_id = {table}.class_level_id "
            f"WHERE {table}.class_level_id IS NOT NULL "
            f"ORDER BY a.full_name"
        )
    ).fetchall()
    best: dict[uuid.UUID, uuid.UUID] = {}
    for _row_id, level_id, arm_id in rows:
        best.setdefault(level_id, arm_id)
    for row_id, _level_id, _arm_id in rows:
        bind.execute(
            sa.text(f"UPDATE {table} SET class_arm_id = :arm WHERE id = :id").bindparams(
                sa.bindparam("arm", value=best[_level_id], type_=sa.Uuid()),
                sa.bindparam("id", value=row_id, type_=sa.Uuid()),
            )
        )


def _reattach_components(bind) -> None:
    """assessment_components already has ``class_arm_id`` — move level-scoped rows
    onto the first arm of their level, deleting orphans that can't be placed."""
    rows = bind.execute(
        sa.text(
            "SELECT ac.id, ac.class_level_id, a.id AS arm_id "
            "FROM assessment_components ac "
            "LEFT JOIN class_arms a ON a.class_level_id = ac.class_level_id "
            "WHERE ac.class_level_id IS NOT NULL ORDER BY a.full_name"
        )
    ).fetchall()
    best: dict[uuid.UUID, uuid.UUID] = {}
    for _comp_id, level_id, arm_id in rows:
        if arm_id is not None:
            best.setdefault(level_id, arm_id)
    for comp_id, level_id, _arm_id in rows:
        if best.get(level_id) is not None:
            bind.execute(
                sa.text(
                    "UPDATE assessment_components SET class_arm_id = :arm WHERE id = :id"
                ).bindparams(
                    sa.bindparam("arm", value=best[level_id], type_=sa.Uuid()),
                    sa.bindparam("id", value=comp_id, type_=sa.Uuid()),
                )
            )
    bind.execute(
        sa.text(
            "DELETE FROM assessment_components "
            "WHERE class_level_id IS NOT NULL AND class_arm_id IS NULL"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()

    # Arms are still attached to their level here, so first promote the arm
    # letter to a full class label (old data: name="A", full_name="JSS 1 A").
    bind.execute(sa.text("UPDATE class_arms SET name = full_name WHERE name <> full_name"))

    # --- subject_offerings: per-level rows → per-arm rows ------------------------
    op.add_column("subject_offerings", sa.Column("class_arm_id", sa.Uuid(), nullable=True))
    _attach_to_arm(bind, "subject_offerings")
    op.drop_constraint("uq_offering_level_subject", "subject_offerings", type_="unique")
    op.drop_index("ix_subject_offerings_class_level_id", table_name="subject_offerings")
    op.drop_constraint("subject_offerings_class_level_id_fkey", "subject_offerings", type_="foreignkey")
    op.drop_column("subject_offerings", "class_level_id")
    op.alter_column("subject_offerings", "class_arm_id", nullable=False)
    op.create_unique_constraint(
        "uq_offering_arm_subject",
        "subject_offerings",
        ["school_id", "class_arm_id", "subject_id"],
    )
    op.create_foreign_key(
        "subject_offerings_class_arm_id_fkey",
        "subject_offerings",
        "class_arms",
        ["class_arm_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- lesson_plans ------------------------------------------------------------
    op.add_column("lesson_plans", sa.Column("class_arm_id", sa.Uuid(), nullable=True))
    _attach_to_arm(bind, "lesson_plans")
    op.drop_constraint("uq_lesson_plan_cell", "lesson_plans", type_="unique")
    op.drop_constraint("lesson_plans_class_level_id_fkey", "lesson_plans", type_="foreignkey")
    op.drop_column("lesson_plans", "class_level_id")
    op.alter_column("lesson_plans", "class_arm_id", nullable=False)
    op.create_unique_constraint(
        "uq_lesson_plan_cell",
        "lesson_plans",
        ["school_id", "term_id", "subject_id", "class_arm_id", "topic"],
    )
    op.create_foreign_key(
        "lesson_plans_class_arm_id_fkey",
        "lesson_plans",
        "class_arms",
        ["class_arm_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- question_banks ------------------------------------------------------------
    op.add_column("question_banks", sa.Column("class_arm_id", sa.Uuid(), nullable=True))
    _attach_to_arm(bind, "question_banks")
    op.drop_constraint("uq_question_bank_cell", "question_banks", type_="unique")
    op.drop_constraint("question_banks_class_level_id_fkey", "question_banks", type_="foreignkey")
    op.drop_column("question_banks", "class_level_id")
    op.alter_column("question_banks", "class_arm_id", nullable=False)
    op.create_unique_constraint(
        "uq_question_bank_cell",
        "question_banks",
        ["school_id", "term_id", "subject_id", "class_arm_id", "topic"],
    )
    op.create_foreign_key(
        "question_banks_class_arm_id_fkey",
        "question_banks",
        "class_arms",
        ["class_arm_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- assessment_components: level-scoped rows → an arm ------------------------
    _reattach_components(bind)
    op.drop_index("uq_component_scope_name", table_name="assessment_components")
    op.drop_constraint("assessment_components_class_level_id_fkey", "assessment_components", type_="foreignkey")
    op.drop_column("assessment_components", "class_level_id")
    op.create_index(
        "uq_component_scope_name",
        "assessment_components",
        ["school_id", "term_id", "class_arm_id", "name"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )

    # --- fee_structures -------------------------------------------------------------
    op.drop_constraint("fee_structures_class_level_id_fkey", "fee_structures", type_="foreignkey")
    op.drop_column("fee_structures", "class_level_id")

    # --- class_arms: drop the level column + its constraints --------------------
    op.drop_constraint("uq_class_arm_session_level_name", "class_arms", type_="unique")
    op.drop_constraint("class_arms_class_level_id_fkey", "class_arms", type_="foreignkey")
    op.drop_column("class_arms", "class_level_id")
    op.create_unique_constraint(
        "uq_class_arm_session_name",
        "class_arms",
        ["school_id", "academic_session_id", "name"],
    )

    # --- class_levels -----------------------------------------------------------------
    op.drop_table("class_levels")


def downgrade() -> None:
    # ClassLevel is gone for good — no automated restore of the previous model.
    raise NotImplementedError("ClassLevel removal is not reversible")