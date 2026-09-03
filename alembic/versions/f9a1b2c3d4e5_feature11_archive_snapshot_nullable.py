"""Feature 11: allow new automatic archives without writing archive snapshots.

Revision ID: a9c4e7f1b2d3
Revises: f8a1b2c3d4e5
Create Date: 2026-09-03
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a9c4e7f1b2d3"
down_revision: str | None = "f8a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "task_archives",
        "archive_snapshot",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
    )


def downgrade() -> None:
    # Downgrade compatibility only: rows created by Feature 11 intentionally
    # have no snapshot, so provide an empty JSON object before restoring the
    # historical NOT NULL contract.
    op.execute(
        "UPDATE task_archives SET archive_snapshot = '{}'::jsonb "
        "WHERE archive_snapshot IS NULL"
    )
    op.alter_column(
        "task_archives",
        "archive_snapshot",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
    )
