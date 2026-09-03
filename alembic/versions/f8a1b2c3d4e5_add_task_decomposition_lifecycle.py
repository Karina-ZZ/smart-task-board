"""Add V1.1 accepted-task AI decomposition lifecycle.

Revision ID: f8a1b2c3d4e5
Revises: f7b8c9d0e1f2
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f8a1b2c3d4e5"
down_revision: str | None = "f7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_decomposition_records",
        sa.Column("decomposition_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by_employee_no", sa.String(), nullable=False),
        sa.Column("trigger_type", sa.String(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'invalidated')",
            name="ck_task_decomposition_records_status",
        ),
        sa.CheckConstraint("task_version >= 1", name="ck_task_decomposition_records_task_version"),
        sa.CheckConstraint("node_count >= 0", name="ck_task_decomposition_records_node_count"),
        sa.CheckConstraint("retry_count >= 0", name="ck_task_decomposition_records_retry_count"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"],
            name=op.f("fk_task_decomposition_records_task_id_tasks"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_employee_no"], ["users.employee_no"],
            name=op.f("fk_task_decomposition_records_triggered_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("decomposition_id", name=op.f("pk_task_decomposition_records")),
    )
    op.create_index(
        "ix_task_decomposition_records_task_created",
        "task_decomposition_records", ["task_id", "created_at"],
    )
    op.create_index(
        "ix_task_decomposition_records_status",
        "task_decomposition_records", ["status", "created_at"],
    )
    op.create_index(
        "uq_task_decomposition_records_idempotency",
        "task_decomposition_records", ["task_id", "idempotency_key"], unique=True,
    )
    op.create_index(
        "uq_task_decomposition_records_one_active",
        "task_decomposition_records", ["task_id"], unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.add_column("tasks", sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("decomposition_status", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("latest_decomposition_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_tasks_latest_decomposition_id_task_decomposition_records"),
        "tasks", "task_decomposition_records", ["latest_decomposition_id"], ["decomposition_id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_tasks_effective_at"), "tasks", ["effective_at"])
    op.create_index(op.f("ix_tasks_decomposition_status"), "tasks", ["decomposition_status"])
    op.create_index(op.f("ix_tasks_latest_decomposition_id"), "tasks", ["latest_decomposition_id"])

    op.add_column("task_nodes", sa.Column("decomposition_id", sa.Uuid(), nullable=True))
    op.add_column("task_nodes", sa.Column("source_type", sa.String(), nullable=True))
    op.add_column("task_nodes", sa.Column("blocked_reason", sa.String(), nullable=True))
    op.create_foreign_key(
        op.f("fk_task_nodes_decomposition_id_task_decomposition_records"),
        "task_nodes", "task_decomposition_records", ["decomposition_id"], ["decomposition_id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_task_nodes_decomposition_id"), "task_nodes", ["decomposition_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_task_nodes_decomposition_id"), table_name="task_nodes")
    op.drop_constraint(
        op.f("fk_task_nodes_decomposition_id_task_decomposition_records"),
        "task_nodes", type_="foreignkey",
    )
    op.drop_column("task_nodes", "blocked_reason")
    op.drop_column("task_nodes", "source_type")
    op.drop_column("task_nodes", "decomposition_id")

    op.drop_index(op.f("ix_tasks_latest_decomposition_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_decomposition_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_effective_at"), table_name="tasks")
    op.drop_constraint(
        op.f("fk_tasks_latest_decomposition_id_task_decomposition_records"),
        "tasks", type_="foreignkey",
    )
    op.drop_column("tasks", "latest_decomposition_id")
    op.drop_column("tasks", "decomposition_status")
    op.drop_column("tasks", "effective_at")

    op.drop_index("uq_task_decomposition_records_one_active", table_name="task_decomposition_records")
    op.drop_index("uq_task_decomposition_records_idempotency", table_name="task_decomposition_records")
    op.drop_index("ix_task_decomposition_records_status", table_name="task_decomposition_records")
    op.drop_index("ix_task_decomposition_records_task_created", table_name="task_decomposition_records")
    op.drop_table("task_decomposition_records")
