"""feature13 node assignment state and node reminder types

Revision ID: b1c2d3e4f5a6
Revises: a9c4e7f1b2d3
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a9c4e7f1b2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REMINDER_TYPES = (
    "'pending_acceptance', 'due_soon', 'due_today', 'overdue', "
    "'periodic_progress_report', 'pending_report', 'no_response', "
    "'issue_blocker', 'collaboration', 'returned', 'completion_review', "
    "'change_request', 'node_start', 'node_due'"
)
_OLD_REMINDER_TYPES = (
    "'pending_acceptance', 'due_soon', 'due_today', 'overdue', "
    "'periodic_progress_report', 'pending_report', 'no_response', "
    "'issue_blocker', 'collaboration', 'returned', 'completion_review', "
    "'change_request'"
)


def upgrade() -> None:
    op.add_column(
        "task_nodes",
        sa.Column("assignment_status", sa.String(), nullable=False, server_default="accepted"),
    )
    op.add_column(
        "task_nodes",
        sa.Column("assignment_responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "task_nodes",
        sa.Column("assignment_reject_reason", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_task_nodes_assignment_status",
        "task_nodes",
        "assignment_status IN ('pending', 'accepted', 'rejected')",
    )
    op.alter_column("task_nodes", "assignment_status", server_default=None)
    op.drop_constraint("ck_reminder_rules_type", "reminder_rules", type_="check")
    op.create_check_constraint(
        "ck_reminder_rules_type",
        "reminder_rules",
        f"reminder_type IN ({_REMINDER_TYPES})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_reminder_rules_type", "reminder_rules", type_="check")
    op.create_check_constraint(
        "ck_reminder_rules_type",
        "reminder_rules",
        f"reminder_type IN ({_OLD_REMINDER_TYPES})",
    )
    op.drop_constraint("ck_task_nodes_assignment_status", "task_nodes", type_="check")
    op.drop_column("task_nodes", "assignment_reject_reason")
    op.drop_column("task_nodes", "assignment_responded_at")
    op.drop_column("task_nodes", "assignment_status")
