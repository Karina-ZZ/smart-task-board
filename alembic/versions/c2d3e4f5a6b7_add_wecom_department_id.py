"""add enterprise WeCom department external identifier

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6

Feature: WeCom organization identity baseline.
Responsibilities:
- Persist the external WeCom department identifier without replacing the internal UUID.
- Keep the field nullable for existing/manual departments during staged synchronization.
Does not own: WeCom API calls, login, or contact synchronization.
Plan task: pre-DEV-18 P0 baseline.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "departments",
        sa.Column("wecom_department_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_departments_wecom_department_id",
        "departments",
        ["wecom_department_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_departments_wecom_department_id", table_name="departments")
    op.drop_column("departments", "wecom_department_id")
